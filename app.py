from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import logging
from openai import AzureOpenAI
from sqlalchemy.sql import func
from vector import (clean_collection_name, process_pdf_and_add_to_collection, create_embedding, chroma_client)
import os
import ollama
import json
import tempfile

# Konfiguriere Logging
logging.basicConfig(level=logging.DEBUG)

# Lade Umgebungsvariablen aus .env-Datei
load_dotenv()

# Initialisiere Flask-App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialisiere Datenbank
db = SQLAlchemy(app)

# Konfiguriere Login-Manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Definiere erlaubte Dateierweiterungen und Konfigurationsvariablen
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

# Lade Konfigurationsvariablen aus Umgebungsvariablen
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION")
AZURE_MODEL = os.getenv("AZURE_MODEL", "gpt-35-turbo")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3-gradient:latest")
LABEL_OWNER = os.getenv("LABLE_OWNER", "labels_arvato.json")

# Initialisiere Azure OpenAI Client
azure_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT
)


# Definiere Datenbankmodelle
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)


class Collection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)


class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('collection.id'), nullable=False)
    collection = db.relationship('Collection', backref=db.backref('files', lazy=True))


class SystemPrompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input = db.Column(db.Text, nullable=False)
    output = db.Column(db.Text, nullable=False)
    system_prompt_id = db.Column(db.Integer, db.ForeignKey('system_prompt.id'), nullable=True)
    system_prompt = db.relationship('SystemPrompt', backref=db.backref('conversations', lazy=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())


class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' oder 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    session = db.relationship('ChatSession',
                              backref=db.backref('messages', lazy=True, order_by='ChatMessage.created_at'))


# Initialisiere Wartungsmodus-Variable
maintenance_mode = False


def load_options():
    with open('config/options.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# Füge Labels zum Template-Kontext hinzu
@app.context_processor
def inject_labels():
    return dict(labels=load_labels())


# Lade Labels aus JSON-Datei
def load_labels():
    label_name = "labels_" + os.getenv("LABEL_OWNER", "") + ".json"
    with open(label_name, 'r', encoding='utf-8') as file:
        return json.load(file)


# Funktion zur Textgenerierung (Azure oder Ollama)
def generate_text(service, system_message, user_message):
    if service == 'azure':
        print("Azure")
        response = azure_openai_client.chat.completions.create(
            model=AZURE_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        print(response.choices[0].message.content)
        return response.choices[0].message.content
    else:  # Ollama
        print("Ollama:", OLLAMA_MODEL)
        response = ollama.chat(model=OLLAMA_MODEL, messages=[
            {'role': 'system', 'content': system_message},
            {'role': 'user', 'content': user_message}
        ])
        return response['message']['content']


# Route zum Auflisten der System-Prompts
@app.route('/system_prompts', methods=['GET'])
@login_required
def list_system_prompts():
    prompts = SystemPrompt.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'content': p.content} for p in prompts])


# Route zum Erstellen eines neuen System-Prompts
@app.route('/system_prompts', methods=['POST'])
@login_required
def create_system_prompt():
    data = request.json
    new_prompt = SystemPrompt(name=data['name'], content=data['content'])
    db.session.add(new_prompt)
    db.session.commit()
    return jsonify({'id': new_prompt.id, 'name': new_prompt.name, 'content': new_prompt.content}), 201


# Route zum Abrufen oder Aktualisieren eines System-Prompts
@app.route('/system_prompts/<int:prompt_id>', methods=['GET', 'PUT'])
@login_required
def system_prompt(prompt_id):
    prompt = SystemPrompt.query.get_or_404(prompt_id)

    if request.method == 'GET':
        return jsonify({'id': prompt.id, 'name': prompt.name, 'content': prompt.content})

    elif request.method == 'PUT':
        data = request.json
        prompt.name = data['name']
        prompt.content = data['content']
        db.session.commit()
        return jsonify({'id': prompt.id, 'name': prompt.name, 'content': prompt.content})


# Route zum Löschen eines System-Prompts
@app.route('/system_prompts/<int:prompt_id>', methods=['DELETE'])
@login_required
def delete_system_prompt(prompt_id):
    prompt = SystemPrompt.query.get_or_404(prompt_id)
    db.session.delete(prompt)
    db.session.commit()
    return '', 204


# Route zum Erstellen einer neuen Kollektion
@app.route('/create_collection', methods=['POST'])
@login_required
def create_collection():
    try:
        app.logger.info("Received request to create collection")
        collection_name = clean_collection_name(request.form.get('title'))
        app.logger.debug(f"Cleaned collection name: {collection_name}")

        if not collection_name:
            app.logger.warning("Collection name is missing")
            return jsonify({"error": "Collection name is required"}), 400

        existing_collections = chroma_client.list_collections()
        logging.debug(f"Existing collections: {[collection.name for collection in existing_collections]}")

        if any(collection.name == collection_name for collection in existing_collections):
            logging.debug(f"Collection '{collection_name}' already exists")
            return jsonify({"error": f"Collection '{collection_name}' already exists"}), 400

        if 'pdfs' not in request.files:
            logging.debug("No PDF files provided")
            return jsonify({"error": "No PDF files provided"}), 400

        files = request.files.getlist('pdfs')
        logging.debug(f"Files received: {[file.filename for file in files]}")

        if not files or all(file.filename == '' for file in files):
            logging.debug("No selected PDF files")
            return jsonify({"error": "No selected PDF files"}), 400

        processed_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                logging.debug(f"Saved file '{filename}' to '{file_path}'")

                process_pdf_and_add_to_collection(file_path, collection_name)
                logging.debug(f"Processed file '{filename}' and added to collection '{collection_name}'")

                processed_files.append(filename)
                os.remove(file_path)  # Optional: remove the file after processing
                logging.debug(f"Removed file '{file_path}' after processing")

            else:
                logging.debug(f"Invalid file: {file.filename}")
                return jsonify({"error": f"Invalid file: {file.filename}"}), 400

        return jsonify({
            "message": f"Collection '{collection_name}' created successfully",
            "processed_files": processed_files
        })
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"error": str(e)}), 500


# Route zum Löschen einer Kollektion
@app.route('/delete_collection/<collection_name>', methods=['POST'])
@login_required
def delete_collection(collection_name):
    try:
        chroma_client.delete_collection(name=collection_name)
        return jsonify({'message': f'Collection "{collection_name}" wurde erfolgreich gelöscht.'}), 200
    except Exception as e:
        return jsonify({'message': f'Fehler beim Löschen der Collection: {str(e)}'}), 500


# Lade Benutzer für Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Route zum Abrufen des Wartungsmodus-Status
@app.route('/get_maintenance_status')
@login_required
def get_maintenance_status():
    return jsonify({'maintenance_mode': maintenance_mode})


# Hauptroute für die Anwendung
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    global maintenance_mode
    labels = load_labels()
    system_prompts = SystemPrompt.query.all()
    options = load_options()  # Optionen laden

    if maintenance_mode and request.method == 'GET':
        return render_template('maintenance.html', labels=labels)

    if request.method == 'POST':
        try:
            # Verarbeite POST-Anfrage für Textgenerierung
            form_data = request.form
            prompt = form_data.get('prompt')
            collection_name = form_data.get('collection_name')
            length = form_data.get('text_length', 'mittel')
            tone = form_data.get('tone', 'professionell')
            service = form_data.get('service', 'azure')
            system_prompt_id = form_data.get('system_prompt_id')
            formality = form_data.get('formality', 'formal')

            logging.info(f"Received form data: {form_data}")

            if not collection_name:
                raise ValueError("No collection selected")

            # Suche relevante Dokumente in der ausgewählten Kollektion
            collection = chroma_client.get_collection(name=collection_name)
            results = collection.query(
                query_embeddings=[create_embedding(prompt)],
                n_results=5,
                include=["documents", "metadatas", "distances"]
            )

            context = "\n".join(results["documents"][0])
            citations = [f"{meta.get('source', 'Unknown')} - S. {meta.get('page_number', 'N/A')}"
                         for meta in results["metadatas"][0]]

            selected_system_prompt = SystemPrompt.query.get(system_prompt_id)
            system_message = selected_system_prompt.content if selected_system_prompt else "You are a helpful AI assistant."

            user_message = f"""
Use this context if it's helpful: {context}

Now, respond in German to the following prompt: {prompt}

Keep the text {length}, stick to this tone of voice: {tone}, and use a {formality} level of formality.
""".strip()

            # Generiere Text basierend auf dem Prompt und Kontext
            generated_text = generate_text(service, system_message, user_message)

            logging.info(f"Generated text: {generated_text[:100]}...")  # Log first 100 characters

            # Speichere die Konversation in der Datenbank
            conversation = Conversation(input=prompt, output=generated_text, system_prompt_id=system_prompt_id)
            db.session.add(conversation)
            db.session.commit()

            conversations = Conversation.query.order_by(Conversation.id.desc()).limit(10).all()
            conversations_data = [{'input': conv.input, 'output': conv.output} for conv in conversations]

            response_data = {
                'generated_text': generated_text,
                'citations': citations,
                'conversations': conversations_data,
                'selected_service': service
            }

            logging.info(f"Sending response: {str(response_data)[:500]}...")  # Log first 500 characters of response
            return jsonify(response_data)

        except Exception as e:
            logging.error(f"Error in index: {str(e)}", exc_info=True)
            error_response = {'error': str(e)}
            logging.info(f"Sending error response: {error_response}")
            return jsonify(error_response), 500

    # GET request
    try:
        collections = chroma_client.list_collections()
        conversations = Conversation.query.order_by(Conversation.id.desc()).limit(10).all()
        conversations_data = [{'input': conv.input, 'output': conv.output} for conv in conversations]

        return render_template('index.html',
                               collections=collections,
                               conversations=conversations_data,
                               selected_service='azure',
                               maintenance_mode=maintenance_mode,
                               labels=labels,
                               system_prompts=system_prompts,
                               options=options)  # Optionen an das Template übergeben
    except Exception as e:
        logging.error(f"Error in GET request: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while loading the page'}), 500


# Neue Route zum Umschalten des Wartungsmodus
@app.route('/toggle_maintenance', methods=['POST'])
@login_required
def toggle_maintenance():
    global maintenance_mode
    maintenance_mode = not maintenance_mode
    return jsonify({'status': 'success', 'maintenance': maintenance_mode})


@app.route('/maintenance_status')
def maintenance_status():
    return jsonify({'maintenance': maintenance_mode})


@app.route('/clear_chat_history', methods=['POST'])
@login_required
def clear_chat_history():
    try:
        Conversation.query.delete()
        db.session.commit()
        return jsonify({'message': 'Chatverlauf wurde erfolgreich gelöscht.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Fehler beim Löschen des Chatverlaufs: {str(e)}'}), 500


@app.route('/list_collections')
@login_required
def list_collections():
    collections = chroma_client.list_collections()
    collection_data = []
    for collection in collections:
        # Hole alle Metadaten für die Collection
        all_metadata = collection.get(include=['metadatas'])

        # Extrahiere einzigartige Dateinamen und Beschreibungen
        unique_sources = set()
        unique_descriptions = set()
        for metadata in all_metadata['metadatas']:
            unique_sources.add(metadata['source'])
            unique_descriptions.add(metadata['description'])

        collection_info = {
            'name': collection.name,
            'document_count': len(unique_sources),
            'description': list(unique_descriptions)[0] if unique_descriptions else "Keine Beschreibung verfügbar",
            'files': list(unique_sources),
            'chunk_count': collection.count(),
            'embedding_function': "Default (change if you're using a custom one)",
            'max_tokens_per_chunk': 512  # This is the default value used in your function
        }
        collection_data.append(collection_info)

    return jsonify({'collections': collection_data})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/create_new_session', methods=['POST'])
@login_required
def create_new_session():
    new_session = ChatSession()
    db.session.add(new_session)
    db.session.commit()
    return jsonify({'session_id': new_session.id})


@app.route('/get_sessions')
@login_required
def get_sessions():
    sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).limit(20).all()
    return jsonify({
        'sessions': [{'id': session.id, 'created_at': session.created_at.isoformat()} for session in sessions]
    })


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    labels = load_labels()

    if request.method == 'POST':
        try:
            data = request.json
            message = data.get('message')
            collection_name = data.get('collection_name')
            system_prompt_id = data.get('system_prompt_id')
            session_id = data.get('session_id')

            if not message:
                raise ValueError("No message provided")

            # Erstellen oder Abrufen einer Chat-Sitzung
            if not session_id:
                chat_session = ChatSession()
                db.session.add(chat_session)
                db.session.commit()
                session_id = chat_session.id
            else:
                chat_session = ChatSession.query.get(session_id)
                if not chat_session:
                    raise ValueError("Invalid session ID")

            # Abrufen der Chathistorie für die aktuelle Session
            chat_history = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.created_at).all()

            # Vorbereiten der Chathistorie für die KI
            messages = []
            for msg in chat_history:
                messages.append({"role": msg.role, "content": msg.content})

            # Speichern der Benutzernachricht
            user_message = ChatMessage(session_id=session_id, role='user', content=message)
            db.session.add(user_message)
            messages.append({"role": "user", "content": message})

            if collection_name:
                collection = chroma_client.get_collection(name=collection_name)
                results = collection.query(
                    query_embeddings=[create_embedding(message)],
                    n_results=5,
                    include=["documents", "metadatas", "distances"]
                )
                context = "\n".join(results["documents"][0])
                citations = [f"{meta.get('source', 'Unknown')} - S. {meta.get('page_number', 'N/A')}"
                             for meta in results["metadatas"][0]]
            else:
                context = ""
                citations = []

            if system_prompt_id:
                selected_system_prompt = SystemPrompt.query.get(system_prompt_id)
                system_message = selected_system_prompt.content if selected_system_prompt else "You are a helpful AI assistant."
            else:
                system_message = "You are a helpful AI assistant."

            # Hinzufügen der Systemnachricht und des Kontexts
            messages.insert(0, {"role": "system", "content": system_message})
            if context:
                messages.append({"role": "system", "content": f"Relevant context: {context}"})

            # Generieren der Antwort mit der vollständigen Chathistorie
            response = azure_openai_client.chat.completions.create(
                model=AZURE_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=800,
            )
            generated_text = response.choices[0].message.content

            # Speichern der Assistentenantwort
            assistant_message = ChatMessage(session_id=session_id, role='assistant', content=generated_text)
            db.session.add(assistant_message)

            db.session.commit()

            return jsonify({
                'message': generated_text,
                'citations': citations,
                'session_id': session_id
            })

        except Exception as e:
            logging.error(f"Error in chat: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    # GET request
    try:
        collections = chroma_client.list_collections()
        system_prompts = SystemPrompt.query.all()
        chat_sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).limit(10).all()

        return render_template('chat.html',
                               collections=collections,
                               chat_sessions=chat_sessions,
                               labels=labels,
                               system_prompts=system_prompts)
    except Exception as e:
        logging.error(f"Error in GET request: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while loading the page'}), 500


@app.route('/chat_history/<int:session_id>', methods=['GET'])
@login_required
def chat_history(session_id):
    chat_session = ChatSession.query.get_or_404(session_id)
    messages = [{'role': msg.role, 'content': msg.content} for msg in chat_session.messages]
    return jsonify(messages)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin_username = os.getenv('ADMIN_USERNAME')
        admin_password = os.getenv('ADMIN_PASSWORD')
        if not User.query.filter_by(username=admin_username).first():
            admin_user = User(username=admin_username, password=generate_password_hash(admin_password))
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True, port=5001)