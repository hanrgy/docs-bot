/**
 * Docs Q&A Bot Frontend JavaScript
 */

class DocsBot {
    constructor() {
        this.documents = [];
        this.isUploading = false;
        this.isAsking = false;
        this.queryCache = new Map(); // Cache for recent queries
        this.queryHistory = JSON.parse(localStorage.getItem('queryHistory') || '[]');
        this.maxCacheSize = 50;
        this.maxHistorySize = 100;
        this.initializeEventListeners();
        this.loadDocuments();
        this.checkHealth();
        this.setupQuerySuggestions();
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
                        ${doc.chunks_stored ? `<span><i class="fas fa-cubes mr-1"></i>${doc.chunks_stored} chunks</span>` : ''}
                    </div>
                    ${doc.vector_storage ? 
                        '<div class="text-xs text-green-600 mt-1"><i class="fas fa-check-circle mr-1"></i>Vector indexed</div>' :
                        '<div class="text-xs text-yellow-600 mt-1"><i class="fas fa-exclamation-circle mr-1"></i>Processing...</div>'
                    }
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

        // Check cache first
        const cacheKey = this.getCacheKey(question);
        if (this.queryCache.has(cacheKey)) {
            console.log('Using cached result for:', question);
            const cachedResult = this.queryCache.get(cacheKey);
            this.displayAnswer(cachedResult);
            this.addToQueryHistory(question);
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
            
            // Cache the result
            this.cacheQuery(cacheKey, result);
            
            // Add to history
            this.addToQueryHistory(question);
            
            this.displayAnswer(result);

        } catch (error) {
            this.showToast(`Failed to get answer: ${error.message}`, 'error');
        } finally {
            this.isAsking = false;
            this.hideLoading();
            this.enableAskButton();
        }
    }
    
    getCacheKey(question) {
        // Create a cache key based on question and current documents
        const docIds = this.documents.map(d => d.id).sort().join(',');
        return `${question.toLowerCase().trim()}_${docIds}`;
    }
    
    cacheQuery(key, result) {
        // Implement LRU cache
        if (this.queryCache.size >= this.maxCacheSize) {
            const firstKey = this.queryCache.keys().next().value;
            this.queryCache.delete(firstKey);
        }
        this.queryCache.set(key, result);
    }
    
    addToQueryHistory(question) {
        // Add to history, avoiding duplicates
        const index = this.queryHistory.indexOf(question);
        if (index > -1) {
            this.queryHistory.splice(index, 1);
        }
        this.queryHistory.unshift(question);
        
        // Limit history size
        if (this.queryHistory.length > this.maxHistorySize) {
            this.queryHistory = this.queryHistory.slice(0, this.maxHistorySize);
        }
        
        // Save to localStorage
        localStorage.setItem('queryHistory', JSON.stringify(this.queryHistory));
        this.updateQuerySuggestions();
    }
    
    setupQuerySuggestions() {
        const questionInput = document.getElementById('question-input');
        const suggestionsContainer = this.createSuggestionsContainer();
        
        questionInput.addEventListener('input', (e) => {
            const value = e.target.value.trim();
            if (value.length > 2) {
                this.showQuerySuggestions(value, suggestionsContainer);
            } else {
                suggestionsContainer.style.display = 'none';
            }
        });
        
        questionInput.addEventListener('focus', () => {
            const value = questionInput.value.trim();
            if (value.length > 2) {
                this.showQuerySuggestions(value, suggestionsContainer);
            }
        });
        
        questionInput.addEventListener('blur', () => {
            // Delay hiding to allow click on suggestions
            setTimeout(() => {
                suggestionsContainer.style.display = 'none';
            }, 200);
        });
    }
    
    createSuggestionsContainer() {
        const questionInput = document.getElementById('question-input');
        const container = document.createElement('div');
        container.id = 'query-suggestions';
        container.className = 'absolute z-10 w-full bg-white border border-gray-300 rounded-lg shadow-lg mt-1 max-h-48 overflow-y-auto hidden';
        container.style.display = 'none';
        
        // Position relative to input
        questionInput.parentElement.style.position = 'relative';
        questionInput.parentElement.appendChild(container);
        
        return container;
    }
    
    showQuerySuggestions(input, container) {
        const suggestions = this.getQuerySuggestions(input);
        
        if (suggestions.length === 0) {
            container.style.display = 'none';
            return;
        }
        
        container.innerHTML = suggestions.map(suggestion => `
            <div class="px-4 py-2 hover:bg-blue-50 cursor-pointer border-b border-gray-100 last:border-b-0"
                 onclick="docsBot.selectSuggestion('${suggestion.replace(/'/g, "\\'")}')">
                <div class="text-sm text-gray-900">${suggestion}</div>
                <div class="text-xs text-gray-500">Previous query</div>
            </div>
        `).join('');
        
        container.style.display = 'block';
    }
    
    getQuerySuggestions(input) {
        const inputLower = input.toLowerCase();
        
        // Search in query history
        const historySuggestions = this.queryHistory
            .filter(query => query.toLowerCase().includes(inputLower))
            .slice(0, 5);
        
        // Add smart suggestions based on input
        const smartSuggestions = this.getSmartSuggestions(inputLower);
        
        // Combine and deduplicate
        const allSuggestions = [...new Set([...historySuggestions, ...smartSuggestions])];
        
        return allSuggestions.slice(0, 6);
    }
    
    getSmartSuggestions(input) {
        const suggestions = [];
        
        // Common question patterns
        if (input.includes('what')) {
            suggestions.push('What is the policy on remote work?');
            suggestions.push('What are the requirements for promotion?');
        }
        
        if (input.includes('how')) {
            suggestions.push('How do I submit a time-off request?');
            suggestions.push('How do I access the employee portal?');
        }
        
        if (input.includes('when')) {
            suggestions.push('When are performance reviews conducted?');
            suggestions.push('When do benefits take effect?');
        }
        
        if (input.includes('who')) {
            suggestions.push('Who should I contact for IT support?');
            suggestions.push('Who approves expense reports?');
        }
        
        return suggestions;
    }
    
    selectSuggestion(suggestion) {
        const questionInput = document.getElementById('question-input');
        questionInput.value = suggestion;
        document.getElementById('query-suggestions').style.display = 'none';
        questionInput.focus();
    }
    
    updateQuerySuggestions() {
        // This could trigger an update of the suggestions UI if needed
        // For now, the suggestions are dynamically generated
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

        // Display answer with enhanced formatting
        answerContent.innerHTML = this.formatAnswer(result.answer);

        // Display confidence with enhanced details
        const confidence = Math.round((result.confidence || 0) * 100);
        confidenceBar.style.width = `${confidence}%`;
        confidenceText.textContent = `${confidence}%`;

        // Update confidence bar color and add confidence explanation
        let confidenceClass, confidenceDescription;
        if (confidence >= 80) {
            confidenceClass = 'bg-green-500 h-2 rounded-full transition-all duration-300';
            confidenceDescription = 'High confidence - Multiple reliable sources';
        } else if (confidence >= 60) {
            confidenceClass = 'bg-yellow-500 h-2 rounded-full transition-all duration-300';
            confidenceDescription = 'Medium confidence - Some supporting sources';
        } else {
            confidenceClass = 'bg-red-500 h-2 rounded-full transition-all duration-300';
            confidenceDescription = 'Low confidence - Limited or uncertain information';
        }
        confidenceBar.className = confidenceClass;
        
        // Add confidence description
        const confidenceScore = document.getElementById('confidence-score');
        const existingDesc = confidenceScore.querySelector('.confidence-description');
        if (existingDesc) existingDesc.remove();
        
        const descElement = document.createElement('div');
        descElement.className = 'confidence-description text-xs text-gray-600 mt-1';
        descElement.textContent = confidenceDescription;
        confidenceScore.appendChild(descElement);

        // Display enhanced citations
        if (result.citations && result.citations.length > 0) {
            citationsSection.classList.remove('hidden');
            citationsList.innerHTML = result.citations.map((citation, index) => `
                <div class="citation p-3 rounded-lg cursor-pointer hover:bg-blue-50 transition-colors" 
                     onclick="docsBot.showSource('${citation.doc_id}', '${citation.chunk_id}', '${citation.filename}', \`${citation.text.replace(/`/g, '\\`')}\`)">
                    <div class="flex items-start space-x-3">
                        <span class="bg-blue-600 text-white text-xs px-2 py-1 rounded-full font-medium">${citation.id || index + 1}</span>
                        <div class="flex-1">
                            <div class="flex items-center justify-between">
                                <p class="text-sm font-medium text-gray-900">${citation.filename}</p>
                                <span class="text-xs text-gray-500">${citation.file_type?.toUpperCase() || 'DOC'}</span>
                            </div>
                            <p class="text-sm text-gray-600 mt-1 line-clamp-3">${citation.text.substring(0, 250)}${citation.text.length > 250 ? '...' : ''}</p>
                            <div class="flex items-center justify-between mt-2 text-xs text-gray-500">
                                <span>Relevance: ${Math.round((citation.score || 0) * 100)}%</span>
                                <span><i class="fas fa-external-link-alt mr-1"></i>Click to view source</span>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            citationsSection.classList.add('hidden');
        }
        
        // Add follow-up questions if available
        this.addFollowUpQuestions(result);
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

    showSource(docId, chunkId, filename, sourceText) {
        const sourceModal = document.getElementById('source-modal');
        const modalContent = document.getElementById('modal-content');
        
        const doc = this.documents.find(d => d.id === docId);
        
        modalContent.innerHTML = `
            <div class="space-y-4">
                <div class="border-b pb-4">
                    <h4 class="text-lg font-semibold text-gray-900">${filename || 'Unknown Document'}</h4>
                    ${doc ? `
                        <div class="flex items-center space-x-4 text-sm text-gray-500 mt-2">
                            <span><i class="fas fa-file-alt mr-1"></i>Type: ${doc.file_type.toUpperCase()}</span>
                            <span><i class="fas fa-weight mr-1"></i>Size: ${this.formatFileSize(doc.file_size)}</span>
                            <span><i class="fas fa-align-left mr-1"></i>Words: ${doc.word_count}</span>
                            <span><i class="fas fa-cubes mr-1"></i>Chunk: ${chunkId || 'Unknown'}</span>
                        </div>
                    ` : ''}
                </div>
                
                ${sourceText ? `
                    <div>
                        <h5 class="text-md font-medium text-gray-900 mb-2">Source Content</h5>
                        <div class="bg-gray-50 p-4 rounded-lg border-l-4 border-blue-500 max-h-64 overflow-y-auto">
                            <p class="text-sm text-gray-700 whitespace-pre-wrap">${sourceText}</p>
                        </div>
                    </div>
                ` : `
                    <div>
                        <p class="text-sm text-gray-600">
                            This citation references content from this document. 
                            The specific passage was used to generate the answer.
                        </p>
                    </div>
                `}
                
                <div class="flex items-center justify-between pt-4 border-t">
                    <div class="text-xs text-gray-500">
                        Document ID: ${docId}
                    </div>
                    <button onclick="docsBot.closeModal()" 
                            class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        sourceModal.classList.remove('hidden');
    }
    
    addFollowUpQuestions(result) {
        // Add follow-up questions section if not exists
        let followUpSection = document.getElementById('follow-up-section');
        if (!followUpSection) {
            const answerSection = document.getElementById('answer-section');
            followUpSection = document.createElement('div');
            followUpSection.id = 'follow-up-section';
            followUpSection.className = 'mt-6 pt-4 border-t';
            answerSection.appendChild(followUpSection);
        }
        
        // Generate smart follow-up questions based on the answer
        const followUps = this.generateFollowUpQuestions(result);
        
        if (followUps.length > 0) {
            followUpSection.innerHTML = `
                <h4 class="text-sm font-semibold text-gray-900 mb-3">
                    <i class="fas fa-lightbulb mr-1 text-yellow-500"></i>Suggested Follow-up Questions
                </h4>
                <div class="space-y-2">
                    ${followUps.map(question => `
                        <button onclick="docsBot.askFollowUp('${question.replace(/'/g, "\\'")}'); " 
                                class="w-full text-left p-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors text-sm text-blue-800 border border-blue-200">
                            <i class="fas fa-question-circle mr-2"></i>${question}
                        </button>
                    `).join('')}
                </div>
            `;
        } else {
            followUpSection.innerHTML = '';
        }
    }
    
    generateFollowUpQuestions(result) {
        const followUps = [];
        const answer = result.answer.toLowerCase();
        const citations = result.citations || [];
        
        // Generate contextual follow-ups based on answer content
        if (answer.includes('policy') || answer.includes('rule')) {
            followUps.push('What are the exceptions to this policy?');
            followUps.push('When was this policy last updated?');
        }
        
        if (answer.includes('process') || answer.includes('procedure') || answer.includes('step')) {
            followUps.push('What are the next steps in this process?');
            followUps.push('Who is responsible for this process?');
        }
        
        if (answer.includes('requirement') || answer.includes('must') || answer.includes('need')) {
            followUps.push('What happens if these requirements are not met?');
        }
        
        if (answer.includes('deadline') || answer.includes('time') || answer.includes('schedule')) {
            followUps.push('What are the key deadlines to remember?');
        }
        
        // Add document-specific follow-ups
        if (citations.length > 1) {
            const uniqueDocs = [...new Set(citations.map(c => c.filename))];
            if (uniqueDocs.length > 1) {
                followUps.push('Are there any differences between these documents?');
            }
        }
        
        // Generic helpful follow-ups
        if (followUps.length < 3) {
            followUps.push('Can you provide more details about this topic?');
            followUps.push('Are there any related topics I should know about?');
        }
        
        return followUps.slice(0, 3); // Limit to 3 follow-ups
    }
    
    askFollowUp(question) {
        const questionInput = document.getElementById('question-input');
        questionInput.value = question;
        this.askQuestion();
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
