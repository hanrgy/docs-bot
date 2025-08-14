/**
 * Docs Q&A Bot Frontend JavaScript
 */

class DocsBot {
    constructor() {
        this.documents = [];
        this.isUploading = false;
        this.isAsking = false;
        this.initializeEventListeners();
        this.loadDocuments();
        this.checkHealth();
    }

    initializeEventListeners() {
        // File upload events
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('file-input');
        const browseBtn = document.getElementById('browse-btn');

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = Array.from(e.dataTransfer.files);
            this.handleFileUpload(files);
        });

        // Browse button
        browseBtn.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            this.handleFileUpload(files);
        });

        // Question and answer
        const questionInput = document.getElementById('question-input');
        const askBtn = document.getElementById('ask-btn');

        askBtn.addEventListener('click', () => {
            this.askQuestion();
        });

        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.askQuestion();
            }
        });

        // Modal events
        const closeModal = document.getElementById('close-modal');
        const sourceModal = document.getElementById('source-modal');

        closeModal.addEventListener('click', () => {
            this.closeModal();
        });

        sourceModal.addEventListener('click', (e) => {
            if (e.target === sourceModal) {
                this.closeModal();
            }
        });

        // Health check
        const healthCheckBtn = document.getElementById('health-check');
        healthCheckBtn.addEventListener('click', () => {
            this.checkHealth();
        });
    }

    async handleFileUpload(files) {
        if (this.isUploading) {
            this.showToast('Upload already in progress', 'warning');
            return;
        }

        if (files.length === 0) {
            return;
        }

        // Validate files
        const validFiles = files.filter(file => {
            const isValidType = ['application/pdf', 'text/markdown', 'text/plain'].includes(file.type) ||
                               ['.pdf', '.md', '.txt'].some(ext => file.name.toLowerCase().endsWith(ext));
            const isValidSize = file.size <= 10 * 1024 * 1024; // 10MB

            if (!isValidType) {
                this.showToast(`Invalid file type: ${file.name}`, 'error');
                return false;
            }

            if (!isValidSize) {
                this.showToast(`File too large: ${file.name} (max 10MB)`, 'error');
                return false;
            }

            return true;
        });

        if (validFiles.length === 0) {
            return;
        }

        this.isUploading = true;
        this.showUploadProgress(0, `Uploading ${validFiles.length} file(s)...`);

        try {
            const formData = new FormData();
            validFiles.forEach(file => {
                formData.append('files', file);
            });

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Upload failed');
            }

            const result = await response.json();
            this.showUploadProgress(100, 'Upload complete!');
            
            setTimeout(() => {
                this.hideUploadProgress();
                this.showToast(result.message, 'success');
                this.loadDocuments(); // Refresh document list
            }, 500);

        } catch (error) {
            this.hideUploadProgress();
            this.showToast(`Upload failed: ${error.message}`, 'error');
        } finally {
            this.isUploading = false;
        }
    }

    async loadDocuments() {
        try {
            const response = await fetch('/documents');
            if (!response.ok) {
                throw new Error('Failed to load documents');
            }

            const data = await response.json();
            this.documents = data.documents || [];
            this.updateDocumentList();
            this.updateDocumentCount();
            this.updateEmptyState();

        } catch (error) {
            console.error('Error loading documents:', error);
            this.showToast('Failed to load documents', 'error');
        }
    }

    updateDocumentList() {
        const documentList = document.getElementById('document-list');
        
        if (this.documents.length === 0) {
            documentList.innerHTML = '<p class="text-sm text-gray-500 text-center py-4">No documents uploaded yet</p>';
            return;
        }

        documentList.innerHTML = this.documents.map(doc => `
            <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 truncate">${doc.filename}</p>
                    <div class="flex items-center space-x-4 text-xs text-gray-500">
                        <span><i class="fas fa-file-alt mr-1"></i>${doc.file_type.toUpperCase()}</span>
                        <span><i class="fas fa-weight mr-1"></i>${this.formatFileSize(doc.file_size)}</span>
                        <span><i class="fas fa-align-left mr-1"></i>${doc.word_count} words</span>
                    </div>
                </div>
                <button onclick="docsBot.deleteDocument('${doc.id}')" 
                        class="text-red-500 hover:text-red-700 p-1">
                    <i class="fas fa-trash text-sm"></i>
                </button>
            </div>
        `).join('');
    }

    updateDocumentCount() {
        const countElement = document.getElementById('document-count');
        const count = this.documents.length;
        countElement.textContent = `${count} document${count !== 1 ? 's' : ''}`;
    }

    updateEmptyState() {
        const emptyState = document.getElementById('empty-state');
        const answerSection = document.getElementById('answer-section');
        
        if (this.documents.length === 0) {
            emptyState.classList.remove('hidden');
            answerSection.classList.add('hidden');
        } else {
            emptyState.classList.add('hidden');
        }
    }

    async deleteDocument(docId) {
        if (!confirm('Are you sure you want to delete this document?')) {
            return;
        }

        try {
            const response = await fetch(`/documents/${docId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Delete failed');
            }

            this.showToast('Document deleted successfully', 'success');
            this.loadDocuments(); // Refresh list

        } catch (error) {
            this.showToast(`Failed to delete document: ${error.message}`, 'error');
        }
    }

    async askQuestion() {
        if (this.isAsking) {
            return;
        }

        const questionInput = document.getElementById('question-input');
        const question = questionInput.value.trim();

        if (!question) {
            this.showToast('Please enter a question', 'warning');
            return;
        }

        if (this.documents.length === 0) {
            this.showToast('Please upload documents first', 'warning');
            return;
        }

        this.isAsking = true;
        this.showLoading();
        this.disableAskButton();

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ question })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Query failed');
            }

            const result = await response.json();
            this.displayAnswer(result);

        } catch (error) {
            this.showToast(`Failed to get answer: ${error.message}`, 'error');
        } finally {
            this.isAsking = false;
            this.hideLoading();
            this.enableAskButton();
        }
    }

    displayAnswer(result) {
        const answerSection = document.getElementById('answer-section');
        const answerContent = document.getElementById('answer-content');
        const confidenceBar = document.getElementById('confidence-bar');
        const confidenceText = document.getElementById('confidence-text');
        const citationsSection = document.getElementById('citations-section');
        const citationsList = document.getElementById('citations-list');

        // Show answer section
        answerSection.classList.remove('hidden');
        answerSection.classList.add('fade-in');

        // Display answer
        answerContent.innerHTML = this.formatAnswer(result.answer);

        // Display confidence
        const confidence = Math.round((result.confidence || 0) * 100);
        confidenceBar.style.width = `${confidence}%`;
        confidenceText.textContent = `${confidence}%`;

        // Update confidence bar color
        if (confidence >= 80) {
            confidenceBar.className = 'bg-green-500 h-2 rounded-full transition-all duration-300';
        } else if (confidence >= 60) {
            confidenceBar.className = 'bg-yellow-500 h-2 rounded-full transition-all duration-300';
        } else {
            confidenceBar.className = 'bg-red-500 h-2 rounded-full transition-all duration-300';
        }

        // Display citations
        if (result.citations && result.citations.length > 0) {
            citationsSection.classList.remove('hidden');
            citationsList.innerHTML = result.citations.map((citation, index) => `
                <div class="citation p-3 rounded-lg cursor-pointer" onclick="docsBot.showSource('${citation.doc_id}', '${citation.chunk_id}')">
                    <div class="flex items-start space-x-3">
                        <span class="bg-blue-600 text-white text-xs px-2 py-1 rounded-full">${index + 1}</span>
                        <div class="flex-1">
                            <p class="text-sm font-medium text-gray-900">${citation.filename}</p>
                            <p class="text-sm text-gray-600 mt-1">${citation.text.substring(0, 200)}...</p>
                            <div class="flex items-center mt-2 text-xs text-gray-500">
                                <span>Relevance: ${Math.round(citation.score * 100)}%</span>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            citationsSection.classList.add('hidden');
        }
    }

    formatAnswer(answer) {
        // Basic markdown-like formatting
        return answer
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^(.*)$/, '<p>$1</p>');
    }

    showSource(docId, chunkId) {
        // For MVP, show a simple modal with document info
        const sourceModal = document.getElementById('source-modal');
        const modalContent = document.getElementById('modal-content');
        
        const doc = this.documents.find(d => d.id === docId);
        if (doc) {
            modalContent.innerHTML = `
                <div class="space-y-4">
                    <div class="border-b pb-4">
                        <h4 class="text-lg font-semibold text-gray-900">${doc.filename}</h4>
                        <div class="flex items-center space-x-4 text-sm text-gray-500 mt-2">
                            <span>Type: ${doc.file_type.toUpperCase()}</span>
                            <span>Size: ${this.formatFileSize(doc.file_size)}</span>
                            <span>Words: ${doc.word_count}</span>
                        </div>
                    </div>
                    <div>
                        <p class="text-sm text-gray-600">
                            This citation references content from this document. 
                            Click the citation in the answer to see the specific passage.
                        </p>
                    </div>
                </div>
            `;
        } else {
            modalContent.innerHTML = '<p class="text-gray-600">Document not found.</p>';
        }
        
        sourceModal.classList.remove('hidden');
    }

    closeModal() {
        const sourceModal = document.getElementById('source-modal');
        sourceModal.classList.add('hidden');
    }

    async checkHealth() {
        const healthCheckBtn = document.getElementById('health-check');
        
        try {
            const response = await fetch('/health');
            const result = await response.json();
            
            if (result.status === 'healthy') {
                healthCheckBtn.className = 'text-sm bg-green-100 text-green-800 px-3 py-1 rounded-full';
                healthCheckBtn.innerHTML = '<i class="fas fa-heartbeat mr-1"></i>Healthy';
            } else {
                healthCheckBtn.className = 'text-sm bg-red-100 text-red-800 px-3 py-1 rounded-full';
                healthCheckBtn.innerHTML = '<i class="fas fa-exclamation-triangle mr-1"></i>Issues';
            }
        } catch (error) {
            healthCheckBtn.className = 'text-sm bg-red-100 text-red-800 px-3 py-1 rounded-full';
            healthCheckBtn.innerHTML = '<i class="fas fa-times mr-1"></i>Error';
        }
    }

    showUploadProgress(percent, text) {
        const progressContainer = document.getElementById('upload-progress');
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        
        progressContainer.classList.remove('hidden');
        progressBar.style.width = `${percent}%`;
        progressText.textContent = text;
    }

    hideUploadProgress() {
        const progressContainer = document.getElementById('upload-progress');
        progressContainer.classList.add('hidden');
    }

    showLoading() {
        const loadingState = document.getElementById('loading-state');
        const answerSection = document.getElementById('answer-section');
        
        loadingState.classList.remove('hidden');
        answerSection.classList.add('hidden');
    }

    hideLoading() {
        const loadingState = document.getElementById('loading-state');
        loadingState.classList.add('hidden');
    }

    disableAskButton() {
        const askBtn = document.getElementById('ask-btn');
        askBtn.disabled = true;
        askBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Asking...';
    }

    enableAskButton() {
        const askBtn = document.getElementById('ask-btn');
        askBtn.disabled = false;
        askBtn.innerHTML = '<i class="fas fa-paper-plane mr-1"></i>Ask';
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        const toastId = 'toast-' + Date.now();
        
        const bgColor = {
            'success': 'bg-green-600',
            'error': 'bg-red-600',
            'warning': 'bg-yellow-600',
            'info': 'bg-blue-600'
        }[type] || 'bg-blue-600';

        const icon = {
            'success': 'fas fa-check',
            'error': 'fas fa-times',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info'
        }[type] || 'fas fa-info';

        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `${bgColor} text-white px-6 py-4 rounded-lg shadow-lg transform translate-x-full transition-transform duration-300`;
        toast.innerHTML = `
            <div class="flex items-center space-x-3">
                <i class="${icon}"></i>
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Animate in
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 100);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (document.getElementById(toastId)) {
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.docsBot = new DocsBot();
});
