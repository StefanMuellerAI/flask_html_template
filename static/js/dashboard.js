document.addEventListener('DOMContentLoaded', function() {
    // DOM Element Selectors
    const elements = {
        collectionForm: document.getElementById('collectionForm'),
        messageDiv: document.getElementById('message'),
        collectionList: document.getElementById('collectionList'),
        clearChatHistoryButton: document.getElementById('clearChatHistory'),
        spinner: document.getElementById('spinner'),
        collectionModal: document.getElementById('collectionModal'),
        modalTitle: document.getElementById('modalTitle'),
        modalContent: document.getElementById('modalContent'),
        closeCollectionModal: document.getElementById('closeCollectionModal'),
        deleteCollectionButton: document.getElementById('deleteCollection'),
        maintenanceButton: document.getElementById('maintenanceButton'),
        systemPromptList: document.getElementById('systemPromptList'),
        addSystemPromptButton: document.getElementById('addSystemPrompt'),
        systemPromptModal: document.getElementById('systemPromptModal'),
        systemPromptModalTitle: document.getElementById('systemPromptModalTitle'),
        systemPromptName: document.getElementById('systemPromptName'),
        systemPromptContent: document.getElementById('systemPromptContent'),
        saveSystemPromptButton: document.getElementById('saveSystemPrompt'),
        closeSystemPromptModalButton: document.getElementById('closeSystemPromptModal')
    };

    let currentPromptId = null;

    // Helper Functions
    function showSpinner() {
        if (elements.spinner) elements.spinner.classList.remove('hidden');
    }

    function hideSpinner() {
        if (elements.spinner) elements.spinner.classList.add('hidden');
    }

    function showMessage(message) {
        if (elements.messageDiv) elements.messageDiv.textContent = message;
    }

    // Main Functions
    function loadExistingCollections() {
        fetch('/list_collections')
            .then(response => response.json())
            .then(data => {
                if (elements.collectionList) {
                    elements.collectionList.innerHTML = '';
                    data.collections.forEach(collection => {
                        const div = document.createElement('div');
                        div.className = 'mb-4 p-3 border border-gray-300 dark:border-gray-600 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition duration-300 ease-in-out';
                        div.innerHTML = `
                            <strong class="text-gray-700 dark:text-gray-300">Text Basis Name:</strong> <span class="text-gray-600 dark:text-gray-400">${collection.name}</span>
                            <br>
                            <strong class="text-gray-700 dark:text-gray-300">Documents:</strong> <span class="text-gray-600 dark:text-gray-400">${collection.document_count}</span>
                            <br>
                            <strong class="text-gray-700 dark:text-gray-300">Chunks:</strong> <span class="text-gray-600 dark:text-gray-400">${collection.chunk_count}</span>
                        `;
                        div.onclick = function() {
                            openCollectionModal(collection);
                        };
                        elements.collectionList.appendChild(div);
                    });
                }
            })
            .catch(error => console.error('Error loading collections:', error));
    }

    function openCollectionModal(collection) {
        if (elements.modalTitle) elements.modalTitle.textContent = `Collection: ${collection.name}`;
        if (elements.modalContent) {
            elements.modalContent.innerHTML = `
                <p><strong>Description:</strong> ${collection.description}</p>
                <p><strong>Number of Documents:</strong> ${collection.document_count}</p>
                <p><strong>Number of Chunks:</strong> ${collection.chunk_count}</p>
                <p><strong>Embedding Function:</strong> ${collection.embedding_function}</p>
                <p><strong>Max Tokens per Chunk:</strong> ${collection.max_tokens_per_chunk}</p>
                <p><strong>Files:</strong></p>
                <ul>
                    ${collection.files.map(file => `<li>${file}</li>`).join('')}
                </ul>
            `;
        }
        if (elements.collectionModal) elements.collectionModal.classList.remove('hidden');
    }

    function closeModal() {
        if (elements.collectionModal) elements.collectionModal.classList.add('hidden');
    }

    function toggleMaintenanceMode() {
    fetch('/toggle_maintenance', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            updateMaintenanceButton(data.maintenance);
            if (data.maintenance) {
                alert('Wartungsmodus ist jetzt aktiv. Die Seite wird neu geladen.');
                location.reload();
            }
        } else {
            throw new Error('Fehler beim Umschalten des Wartungsmodus');
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        elements.maintenanceButton.textContent = 'Fehler beim Umschalten';
        elements.maintenanceButton.classList.add('bg-red-500', 'hover:bg-red-700');
        setTimeout(() => {
            elements.maintenanceButton.textContent = 'Wartungsmodus umschalten';
            elements.maintenanceButton.classList.remove('bg-red-500', 'hover:bg-red-700');
            elements.maintenanceButton.classList.add('bg-blue-500', 'hover:bg-blue-700');
        }, 2000);
    });
}

function updateMaintenanceButton(isMaintenanceMode) {
    elements.maintenanceButton.textContent = isMaintenanceMode
        ? 'Wartungsmodus ausschalten'
        : 'Wartungsmodus einschalten';
    elements.maintenanceButton.classList.toggle('bg-red-500', isMaintenanceMode);
    elements.maintenanceButton.classList.toggle('bg-blue-500', !isMaintenanceMode);
}

function loadMaintenanceStatus() {
    fetch('/maintenance_status')
        .then(response => response.json())
        .then(data => {
            updateMaintenanceButton(data.maintenance);
        })
        .catch(error => console.error('Error loading maintenance status:', error));
}

// Fügen Sie dies zur Liste der initial geladenen Funktionen hinzu
loadMaintenanceStatus();

    function loadSystemPrompts() {
        fetch('/system_prompts')
            .then(response => response.json())
            .then(prompts => {
                if (elements.systemPromptList) {
                    elements.systemPromptList.innerHTML = '';
                    prompts.forEach(prompt => {
                        const promptElement = document.createElement('div');
                        promptElement.className = 'flex justify-between items-center p-2 border rounded';
                        promptElement.innerHTML = `
                            <span>${prompt.name}</span>
                            <div>
                                <button class="edit-prompt bg-blue-500 hover:bg-blue-700 text-white font-bold py-1 px-2 rounded mr-2" data-id="${prompt.id}">Edit</button>
                                <button class="delete-prompt bg-red-500 hover:bg-red-700 text-white font-bold py-1 px-2 rounded" data-id="${prompt.id}">Delete</button>
                            </div>
                        `;
                        elements.systemPromptList.appendChild(promptElement);
                    });
                }
            });
    }

    function openSystemPromptModal(title, name = '', content = '') {
        elements.systemPromptModalTitle.textContent = title;
        elements.systemPromptName.value = name;
        elements.systemPromptContent.value = content;
        elements.systemPromptModal.classList.remove('hidden');
    }

    function closeSystemPromptModal() {
        elements.systemPromptModal.classList.add('hidden');
        currentPromptId = null;
    }

    // Event Listeners
    if (elements.collectionForm) {
        elements.collectionForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);

            showSpinner();
            showMessage('');

            fetch('/create_collection', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                hideSpinner();
                showMessage(data.message);
                elements.collectionForm.reset();
                loadExistingCollections();
            })
            .catch(error => {
                hideSpinner();
                console.error('Error:', error);
                showMessage('An error occurred. Please try again.');
            });
        });
    }

    if (elements.clearChatHistoryButton) {
        elements.clearChatHistoryButton.addEventListener('click', function() {
            if (confirm('Are you sure you want to delete the entire chat history?')) {
                fetch('/clear_chat_history', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while deleting the chat history.');
                });
            }
        });
    }

    if (elements.closeCollectionModal) {
        elements.closeCollectionModal.addEventListener('click', closeModal);
    }

    if (elements.deleteCollectionButton) {
        elements.deleteCollectionButton.addEventListener('click', function() {
            const collectionName = elements.modalTitle ? elements.modalTitle.textContent.split(': ')[1] : '';
            if (confirm(`Are you sure you want to delete the collection "${collectionName}"?`)) {
                fetch(`/delete_collection/${collectionName}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    closeModal();
                    loadExistingCollections();
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while deleting the collection.');
                });
            }
        });
    }

    if (elements.maintenanceButton) {
        elements.maintenanceButton.addEventListener('click', toggleMaintenanceMode);
    }

    if (elements.addSystemPromptButton) {
        elements.addSystemPromptButton.addEventListener('click', () => openSystemPromptModal('Add System Prompt'));
    }

    if (elements.closeSystemPromptModalButton) {
        elements.closeSystemPromptModalButton.addEventListener('click', closeSystemPromptModal);
    }

    if (elements.saveSystemPromptButton) {
        elements.saveSystemPromptButton.addEventListener('click', () => {
            const promptData = {
                name: elements.systemPromptName.value,
                content: elements.systemPromptContent.value
            };

            const url = currentPromptId ? `/system_prompts/${currentPromptId}` : '/system_prompts';
            const method = currentPromptId ? 'PUT' : 'POST';

            fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(promptData),
            })
            .then(response => response.json())
            .then(() => {
                loadSystemPrompts();
                closeSystemPromptModal();
            });
        });
    }

    if (elements.systemPromptList) {
        elements.systemPromptList.addEventListener('click', (e) => {
            if (e.target.classList.contains('edit-prompt')) {
                const promptId = e.target.getAttribute('data-id');
                fetch(`/system_prompts/${promptId}`)
                    .then(response => response.json())
                    .then(prompt => {
                        currentPromptId = prompt.id;
                        openSystemPromptModal('Edit System Prompt', prompt.name, prompt.content);
                    });
            } else if (e.target.classList.contains('delete-prompt')) {
                const promptId = e.target.getAttribute('data-id');
                if (confirm('Are you sure you want to delete this system prompt?')) {
                    fetch(`/system_prompts/${promptId}`, { method: 'DELETE' })
                        .then(() => loadSystemPrompts());
                }
            }
        });
    }

    // Close the modal if clicked outside
    window.onclick = function(event) {
        if (event.target == elements.collectionModal) {
            closeModal();
        }
        if (event.target == elements.systemPromptModal) {
            closeSystemPromptModal();
        }
    }

    // Initial load
    loadExistingCollections();
    loadSystemPrompts();
});