document.addEventListener('DOMContentLoaded', function() {
    const elements = {
        inputForm: document.getElementById('inputForm'),
        outputDiv: document.getElementById('output'),
        outputContainer: document.getElementById('outputContainer'),
        spinnerDiv: document.getElementById('spinner'),
        chatHistoryDiv: document.getElementById('chatHistory'),
        modal: document.getElementById('chatModal'),
        modalTitle: document.getElementById('modalTitle'),
        modalContent: document.getElementById('modalContent'),
        closeModalButton: document.getElementById('closeModal'),
        copyButton: document.getElementById('copyButton'),
        modalCopyButton: document.getElementById('modalCopyButton'),
        copyButtonContainer: document.getElementById('copyButtonContainer'),
        citationsContainer: document.getElementById('citationsContainer'),
        collectionSelect: document.getElementById('collection_name'),
        systemPromptSelect: document.getElementById('system_prompt_id'),
        generateButton: document.getElementById('generateButton'),
        textLengthInputs: document.querySelectorAll('input[name="text_length"]'),
        toneInputs: document.querySelectorAll('input[name="tone"]'),
        promptTextarea: document.getElementById('prompt'),
        toggleSourcesButton: document.getElementById('toggleSources'),
        sourcesContent: document.getElementById('sourcesContent')
    };

    let conversationsData = [];

    function loadInitialConversations() {
        const conversationsScript = document.getElementById('conversations-data');
        if (conversationsScript) {
            conversationsData = JSON.parse(conversationsScript.textContent);
        }
    }

    function showSpinner() {
        elements.spinnerDiv.classList.remove('hidden');
    }

    function hideSpinner() {
        elements.spinnerDiv.classList.add('hidden');
    }

    function generateText() {
        const formData = new FormData(elements.inputForm);

        showSpinner();
        elements.copyButtonContainer.classList.add('hidden');

        fetch('/', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            elements.outputDiv.textContent = data.generated_text;
            if (elements.outputDiv.textContent.trim() !== '') {
                elements.copyButtonContainer.classList.remove('hidden');
            }
            updateSources(data.citations);
            updateChatHistory(data.conversations);
            conversationsData = data.conversations;
            hideSpinner();
        })
        .catch(error => {
            console.error('Error:', error);
            elements.outputDiv.textContent = 'Ein Fehler ist aufgetreten: ' + error.message;
            elements.copyButtonContainer.classList.add('hidden');
            hideSpinner();
        });
    }

    function updateSources(citations) {
        elements.citationsContainer.innerHTML = citations.map(citation => `<p>${citation}</p>`).join('');
        elements.sourcesContent.classList.add('hidden');
        elements.toggleSourcesButton.querySelector('svg').classList.remove('rotate-180');
    }

    function updateChatHistory(conversations) {
        const totalConversations = conversations.length;
        elements.chatHistoryDiv.innerHTML = conversations.map((conv, index) => {
            const conversationNumber = totalConversations - index;
            return `
                <div class="mb-4 p-3 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition duration-300 ease-in-out" onclick="openModal(${index})">
                    <span class="text-gray-500 dark:text-gray-400 float-right">#${conversationNumber}</span>
                    <strong>Input:</strong> <span class="text-gray-600 dark:text-gray-400">${conv.input.substring(0, 50)}...</span><br>
                    <strong>Output:</strong> <span class="text-gray-600 dark:text-gray-400">${conv.output.substring(0, 50)}...</span>
                </div>
            `;
        }).join('');
    }

    function openModal(index) {
        const conversation = conversationsData[index];
        const totalConversations = conversationsData.length;
        const conversationNumber = totalConversations - index;
        elements.modalTitle.textContent = `Conversation ${conversationNumber}`;
        elements.modalContent.innerHTML = `
            <div class="text-left">
                <p class="font-bold mb-2">Input:</p>
                <p class="mb-4">${conversation.input}</p>
                <p class="font-bold mb-2">Output:</p>
                <div class="max-h-[40vh] overflow-y-auto border p-2 rounded">${conversation.output}</div>
            </div>
        `;
        elements.modal.classList.remove('hidden');
    }

    function closeModal() {
        elements.modal.classList.add('hidden');
    }

    function copyToClipboard(button, textToCopy) {
        var originalText = button.innerHTML;
        var originalClasses = button.className;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textToCopy).then(function() {
                button.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>Kopiert!';
                button.className = originalClasses.replace('bg-blue-500 hover:bg-blue-700', 'bg-green-500 hover:bg-green-700');

                setTimeout(function() {
                    button.innerHTML = originalText;
                    button.className = originalClasses;
                }, 2000);
            }, function(err) {
                console.error('Fehler beim Kopieren des Textes: ', err);
                button.textContent = 'Fehler beim Kopieren';
                button.className = originalClasses.replace('bg-blue-500 hover:bg-blue-700', 'bg-red-500 hover:bg-red-700');
            });
        } else {
            // Fallback für ältere Browser (z.B. Internet Explorer)
            var textarea = document.createElement('textarea');
            textarea.value = textToCopy;

            // Stil setzen, um das Textarea unsichtbar zu machen
            textarea.style.position = 'fixed';
            textarea.style.top = 0;
            textarea.style.left = 0;
            textarea.style.width = '1px';
            textarea.style.height = '1px';
            textarea.style.padding = 0;
            textarea.style.border = 'none';
            textarea.style.outline = 'none';
            textarea.style.boxShadow = 'none';
            textarea.style.background = 'transparent';

            document.body.appendChild(textarea);
            textarea.select();

            try {
                var successful = document.execCommand('copy');
                if (successful) {
                    button.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
                        '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>Kopiert!';
                    button.className = originalClasses.replace('bg-blue-500 hover:bg-blue-700', 'bg-green-500 hover:bg-green-700');

                    setTimeout(function() {
                        button.innerHTML = originalText;
                        button.className = originalClasses;
                    }, 2000);
                } else {
                    throw new Error('Copy command war nicht erfolgreich');
                }
            } catch (err) {
                console.error('Fehler beim Kopieren des Textes: ', err);
                button.textContent = 'Fehler beim Kopieren';
                button.className = originalClasses.replace('bg-blue-500 hover:bg-blue-700', 'bg-red-500 hover:bg-red-700');
            }

            document.body.removeChild(textarea);
        }
    }

    // Event Listeners
    if (elements.inputForm) {
        elements.inputForm.addEventListener('submit', function(e) {
            e.preventDefault();
            generateText();
        });
    }

    if (elements.copyButton) {
        elements.copyButton.addEventListener('click', function() {
            copyToClipboard(this, elements.outputDiv.textContent);
        });
    }

    if (elements.modalCopyButton) {
        elements.modalCopyButton.addEventListener('click', function() {
            copyToClipboard(this, elements.modalContent.textContent);
        });
    }

    if (elements.closeModalButton) {
        elements.closeModalButton.addEventListener('click', closeModal);
    }

    if (elements.toggleSourcesButton) {
        elements.toggleSourcesButton.addEventListener('click', function() {
            elements.sourcesContent.classList.toggle('hidden');
            this.querySelector('svg').classList.toggle('rotate-180');
        });
    }

    // Close modal when clicking outside
    window.onclick = function(event) {
        if (event.target == elements.modal) {
            closeModal();
        }
    }

    // Initialize copy buttons
    const copyButtons = document.querySelectorAll('.copy-button');
    copyButtons.forEach(button => {
        button.classList.add('bg-blue-500', 'hover:bg-blue-700');
    });

    // Load initial conversations
    loadInitialConversations();

    // Make openModal function global
    window.openModal = openModal;
});