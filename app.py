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



#ollama.pull('llama3-gradient:latest')

# Configure logging
logging.basicConfig(level=logging.DEBUG)


load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_MODEL = os.getenv("AZURE_MODEL", "gpt-35-turbo")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3-gradient:latest")
LABEL_OWNER = os.getenv("LABLE_OWNER", "labels_arvato.json")

azure_openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-15-preview",
    azure_endpoint=AZURE_ENDPOINT
)

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


maintenance_mode = False


@app.context_processor
def inject_labels():
    return dict(labels=load_labels())

def load_labels():
    label_name = "labels_" + os.getenv("LABEL_OWNER", "") + ".json"
    with open(label_name, 'r', encoding='utf-8') as file:
        return json.load(file)


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

@app.route('/system_prompts', methods=['GET'])
@login_required
def list_system_prompts():
    prompts = SystemPrompt.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'content': p.content} for p in prompts])

@app.route('/system_prompts', methods=['POST'])
@login_required
def create_system_prompt():
    data = request.json
    new_prompt = SystemPrompt(name=data['name'], content=data['content'])
    db.session.add(new_prompt)
    db.session.commit()
    return jsonify({'id': new_prompt.id, 'name': new_prompt.name, 'content': new_prompt.content}), 201


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

@app.route('/system_prompts/<int:prompt_id>', methods=['DELETE'])
@login_required
def delete_system_prompt(prompt_id):
    prompt = SystemPrompt.query.get_or_404(prompt_id)
    db.session.delete(prompt)
    db.session.commit()
    return '', 204



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

@app.route('/delete_collection/<collection_name>', methods=['POST'])
@login_required
def delete_collection(collection_name):
    try:
        chroma_client.delete_collection(name=collection_name)
        return jsonify({'message': f'Collection "{collection_name}" wurde erfolgreich gelöscht.'}), 200
    except Exception as e:
        return jsonify({'message': f'Fehler beim Löschen der Collection: {str(e)}'}), 500

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/get_maintenance_status')
@login_required
def get_maintenance_status():
    return jsonify({'maintenance_mode': maintenance_mode})


from flask import jsonify, request, render_template
import logging


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    global maintenance_mode
    labels = load_labels()
    system_prompts = SystemPrompt.query.all()

    if maintenance_mode and request.method == 'GET':
        return render_template('maintenance.html', labels=labels)

    if request.method == 'POST':
        try:
            form_data = request.form
            prompt = form_data.get('prompt')
            collection_name = form_data.get('collection_name')
            length = form_data.get('length', 'mittel')
            tone = form_data.get('tone', 'professionell')
            service = form_data.get('service', 'azure')
            system_prompt_id = form_data.get('system_prompt_id')

            logging.info(f"Received form data: {form_data}")

            if not collection_name:
                raise ValueError("No collection selected")

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

            user_message = f"Use this context if it's helpful: {context}\n\nNow, respond in german to the following prompt: {prompt}\nKeep the text {length} and stick to this tone of voice for the text: {tone}."

            generated_text = generate_text(service, system_message, user_message)

            logging.info(f"Generated text: {generated_text[:100]}...")  # Log first 100 characters

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
                               system_prompts=system_prompts)
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