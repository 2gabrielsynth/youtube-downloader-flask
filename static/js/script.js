/**
 * YouTube Downloader - Classe Principal
 * Versão: 2.0.0
 * Autor: Gabriel Machado
 * Data: 2024
 */

class YouTubeDownloader {
    constructor() {
        // Estado da aplicação
        this.state = {
            sessionId: null,
            downloadId: null,
            selectedOption: null,
            currentDownloadUrl: null,
            isDownloading: false,
            pollInterval: null
        };

        // Cache de elementos DOM
        this.elements = {};

        // Configurações
        this.config = {
            pollInterval: 1000,
            maxRetries: 3,
            retryDelay: 2000
        };

        this.init();
    }

    // ========== INICIALIZAÇÃO ==========
    init() {
        this.cacheElements();
        this.bindEvents();
        this.setupUI();
        
        console.log('✅ YouTube Downloader inicializado');
    }

    cacheElements() {
        // Seletores organizados por categoria
        const selectors = {
            // Inputs principais
            inputs: {
                url: '#urlInput',
                filename: '#filenameInput'
            },
            
            // Botões principais
            buttons: {
                paste: '#pasteBtn',
                getInfo: '#getInfoBtn',
                download: '#downloadBtn',
                refresh: '#refreshDownloadsBtn',
                clearLogs: '#clearLogsBtn',
                clearDownloads: '#clearDownloadsBtn',
                cleanup: '#manualCleanupBtn',
                pause: '#pauseBtn',
                cancel: '#cancelBtn',
                openFile: '#openFileBtn',
                downloadFile: '#downloadFileBtn',
                modalClose: '.modal-close',
                stats: '#showStatsBtn'
            },
            
            // Cards/seções
            cards: {
                videoInfo: '#videoInfoCard',
                progress: '#progressCard',
                downloads: '#downloadsCard'
            },
            
            // Elementos de informação
            info: {
                videoTitle: '#videoTitle',
                videoAuthor: '#videoAuthor',
                videoDuration: '#videoDuration',
                videoViews: '#videoViews',
                videoThumbnail: '#videoThumbnail',
                selectedOption: '#selectedOptionText',
                sessionId: '#sessionId',
                statusDot: '#statusDot',
                statusText: '#statusText'
            },
            
            // Progresso
            progress: {
                fill: '#progressFill',
                percentage: '#progressPercentage',
                message: '#progressMessage',
                logOutput: '#logOutput'
            },
            
            // Downloads
            downloads: {
                list: '#downloadsList',
                count: '#downloadCount',
                storageUsed: '#storageUsed'
            },
            
            // Modais
            modals: {
                success: '#successModal',
                successMessage: '#successMessage',
                stats: '#statsModal',
                statsContent: '#statsContent'
            },
            
            // Opções
            options: '.option-card'
        };

        // Cachear todos os elementos
        for (const [category, items] of Object.entries(selectors)) {
            if (category === 'options') {
                this.elements.options = document.querySelectorAll(items);
            } else {
                this.elements[category] = {};
                for (const [key, selector] of Object.entries(items)) {
                    this.elements[category][key] = document.querySelector(selector);
                }
            }
        }
    }

    bindEvents() {
        const { buttons, inputs, modals } = this.elements;

        // Botões principais
        this.safeAddListener(buttons.paste, 'click', () => this.pasteFromClipboard());
        this.safeAddListener(buttons.getInfo, 'click', () => this.getVideoInfo());
        this.safeAddListener(buttons.download, 'click', () => this.startDownload());
        this.safeAddListener(buttons.refresh, 'click', () => this.refreshDownloads());
        this.safeAddListener(buttons.clearLogs, 'click', () => this.clearLogs());
        this.safeAddListener(buttons.cleanup, 'click', () => this.cleanupExpired());
        this.safeAddListener(buttons.stats, 'click', () => this.showStats());

        // Controles de download
        this.safeAddListener(buttons.pause, 'click', () => this.togglePause());
        this.safeAddListener(buttons.cancel, 'click', () => this.cancelDownload());

        // Modal actions
        this.safeAddListener(buttons.openFile, 'click', () => this.openDownloadsFolder());
        this.safeAddListener(buttons.downloadFile, 'click', () => this.downloadCurrentFile());
        this.safeAddListener(buttons.modalClose, 'click', () => this.closeModal());

        // Input events
        this.safeAddListener(inputs.url, 'input', () => this.validateForm());
        
        // Opções de download
        if (this.elements.options) {
            this.elements.options.forEach(card => {
                card.addEventListener('click', () => this.selectOption(card));
            });
        }

        // Eventos globais
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });

        // Fechar modal ao clicar fora
        if (modals.success) {
            modals.success.addEventListener('click', (e) => {
                if (e.target === modals.success) this.closeModal();
            });
        }
    }

    setupUI() {
        this.updateStatus(true, 'Pronto');
        this.refreshDownloads();
        this.validateForm();
    }

    // ========== MÉTODOS UTILITÁRIOS ==========
    safeAddListener(element, event, handler) {
        if (element) {
            element.addEventListener(event, handler);
        }
    }

    updateElement(element, property, value) {
        if (element && element[property] !== undefined) {
            element[property] = value;
        }
    }

    showElement(element) {
        if (element) element.classList.remove('hidden');
    }

    hideElement(element) {
        if (element) element.classList.add('hidden');
    }

    toggleElement(element, force) {
        if (element) {
            element.classList.toggle('hidden', force === false);
        }
    }

    // ========== GERENCIAMENTO DE UI ==========
    updateStatus(connected, message) {
        const { statusDot, statusText } = this.elements.info;
        
        if (statusDot) {
            statusDot.classList.toggle('connected', connected);
            statusDot.classList.toggle('disconnected', !connected);
        }
        
        this.updateElement(statusText, 'textContent', message);
    }

    updateProgress(percent, message = '') {
        const { progress } = this.elements;
        
        if (progress.fill) {
            progress.fill.style.width = `${percent}%`;
        }
        
        if (progress.percentage) {
            progress.percentage.textContent = `${percent.toFixed(1)}%`;
        }
        
        if (progress.message && message) {
            progress.message.textContent = message;
        }
    }

    addLog(message, type = 'info') {
        const { logOutput } = this.elements.progress;
        if (!logOutput) return;

        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        logOutput.appendChild(logEntry);
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    showNotification(message, type = 'info', duration = 3000) {
        // Implementação simples de notificação
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        if (type === 'error') {
            alert(message);
        }
    }

    // ========== LÓGICA DE NEGÓCIO ==========
    async pasteFromClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            this.updateElement(this.elements.inputs.url, 'value', text);
            this.validateForm();
        } catch (error) {
            this.showNotification('Não foi possível acessar a área de transferência', 'error');
        }
    }

    validateForm() {
        const { url } = this.elements.inputs;
        const { download } = this.elements.buttons;
        
        const hasUrl = url && url.value.trim().length > 0;
        const hasOption = this.state.selectedOption !== null;
        
        if (download) {
            download.disabled = !(hasUrl && hasOption);
        }
    }

    selectOption(card) {
        // Remover seleção anterior
        this.elements.options?.forEach(c => c.classList.remove('selected'));
        
        // Selecionar nova opção
        card.classList.add('selected');
        this.state.selectedOption = card.dataset.option;
        
        // Atualizar texto
        this.updateElement(
            this.elements.info.selectedOption, 
            'textContent', 
            this.state.selectedOption
        );
        
        this.validateForm();
    }

    async getVideoInfo() {
        const { url } = this.elements.inputs;
        const { getInfo } = this.elements.buttons;
        const { videoInfo } = this.elements.cards;
        
        if (!url || !url.value.trim()) {
            this.showNotification('Por favor, cole uma URL do YouTube', 'warning');
            return;
        }

        try {
            this.disableButton(getInfo, 'Processando...');
            
            const response = await fetch('/api/get_info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url.value.trim() })
            });

            if (!response.ok) {
                throw new Error(`Erro ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                this.displayVideoInfo(data);
                this.showElement(videoInfo);
                
                if (videoInfo) {
                    videoInfo.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                
                this.addLog('Informações obtidas com sucesso');
            } else {
                this.showNotification(data.error || 'Erro ao obter informações', 'error');
            }
        } catch (error) {
            console.error('Erro:', error);
            this.showNotification('Erro ao obter informações do vídeo', 'error');
        } finally {
            this.enableButton(getInfo, 'Obter Informações');
        }
    }

    displayVideoInfo(data) {
        const { videoTitle, videoAuthor, videoDuration, videoViews, videoThumbnail } = this.elements.info;
        
        this.updateElement(videoTitle, 'textContent', data.title);
        this.updateElement(videoAuthor, 'textContent', data.author);
        this.updateElement(videoDuration, 'textContent', this.formatDuration(data.duration));
        this.updateElement(videoViews, 'textContent', this.formatNumber(data.views));
        
        if (videoThumbnail && data.thumbnail) {
            videoThumbnail.src = data.thumbnail;
            videoThumbnail.style.display = 'block';
        }
    }

    async startDownload() {
        if (!this.state.selectedOption) {
            this.showNotification('Selecione uma opção de download', 'warning');
            return;
        }

        const { url, filename } = this.elements.inputs;
        const { download } = this.elements.buttons;
        const { progress } = this.elements.cards;
        
        if (!url || !url.value.trim()) {
            this.showNotification('Insira uma URL do YouTube', 'warning');
            return;
        }

        try {
            this.state.isDownloading = true;
            this.disableButton(download, 'Iniciando...');

            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url.value.trim(),
                    option: this.state.selectedOption,
                    custom_filename: filename?.value.trim() || null
                })
            });

            // Tratar rate limiting
            if (response.status === 429) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'Muitos downloads ativos. Aguarde.');
            }

            if (!response.ok) {
                throw new Error(`Erro ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                this.state.sessionId = data.session_id;
                this.state.downloadId = data.download_id;
                
                // Mostrar progresso
                this.showElement(progress);
                this.addLog('Download iniciado');
                
                if (progress) {
                    progress.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
                
                // Iniciar polling
                this.startPolling();
            } else {
                this.showNotification(data.error || 'Erro ao iniciar download', 'error');
            }
        } catch (error) {
            console.error('Erro no download:', error);
            this.showNotification(error.message, 'error');
            this.state.isDownloading = false;
        } finally {
            this.enableButton(download, 'Iniciar Download');
        }
    }

    startPolling() {
        this.stopPolling();
        
        this.state.pollInterval = setInterval(async () => {
            if (!this.state.downloadId) return;
            
            try {
                const response = await fetch(`/api/status/${this.state.downloadId}`);
                if (!response.ok) return;
                
                const data = await response.json();
                
                switch (data.status) {
                    case 'downloading':
                        this.updateProgress(data.progress, data.message);
                        if (data.logs?.length > 0) {
                            data.logs.forEach(log => this.addLog(log));
                        }
                        break;
                        
                    case 'completed':
                        this.handleDownloadComplete(data);
                        break;
                        
                    case 'error':
                        this.handleDownloadError(data);
                        break;
                }
            } catch (error) {
                console.error('Erro no polling:', error);
            }
        }, this.config.pollInterval);
    }

    stopPolling() {
        if (this.state.pollInterval) {
            clearInterval(this.state.pollInterval);
            this.state.pollInterval = null;
        }
    }

    handleDownloadComplete(data) {
        this.stopPolling();
        this.state.isDownloading = false;
        
        this.updateProgress(100, 'Concluído!');
        this.state.currentDownloadUrl = `/download/${data.filename}`;
        
        // Mostrar modal de sucesso
        this.showSuccessModal(data);
        
        // Atualizar lista de downloads
        this.refreshDownloads();
        
        // Log
        this.addLog('Download concluído com sucesso!', 'success');
    }

    handleDownloadError(data) {
        this.stopPolling();
        this.state.isDownloading = false;
        
        this.updateProgress(0, 'Erro');
        this.addLog(`ERRO: ${data.message}`, 'error');
        
        this.showNotification('Erro no download: ' + data.message, 'error');
    }

    showSuccessModal(data) {
        const { success, successMessage } = this.elements.modals;
        
        if (successMessage) {
            successMessage.textContent = data.message || 'Download concluído!';
        }
        
        this.showElement(success);
    }

    closeModal() {
        const { success, stats } = this.elements.modals;
        this.hideElement(success);
        this.hideElement(stats);
    }

    async refreshDownloads() {
        try {
            const response = await fetch('/api/my_downloads');
            if (!response.ok) return;
            
            const data = await response.json();
            this.renderDownloadsList(data.files || []);
        } catch (error) {
            console.error('Erro ao carregar downloads:', error);
        }
    }

    renderDownloadsList(files) {
        const { list, count } = this.elements.downloads;
        if (!list) return;
        
        if (files.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-cloud-download-alt"></i>
                    <h3>Nenhum download</h3>
                    <p>Seus downloads aparecerão aqui</p>
                </div>
            `;
            return;
        }
        
        // Atualizar contador
        if (count) {
            count.textContent = files.length;
        }
        
        // Renderizar lista
        list.innerHTML = files.map(file => this.createDownloadItem(file)).join('');
    }

    createDownloadItem(file) {
        const expiresIn = file.expires_in_minutes || 0;
        const sizeMB = file.size_mb || (file.size / (1024 * 1024)).toFixed(2);
        const date = new Date(file.modified).toLocaleString();
        
        return `
            <div class="download-item" data-filename="${file.filename}">
                <div class="download-info">
                    <div class="download-name" title="${file.original_name || file.filename}">
                        ${file.original_name || file.filename}
                    </div>
                    <div class="download-meta">
                        <span><i class="fas fa-weight"></i> ${sizeMB} MB</span>
                        <span><i class="fas fa-calendar"></i> ${date}</span>
                        <span class="expiry-badge ${expiresIn < 30 ? 'warning' : ''}">
                            <i class="fas fa-clock"></i> ${this.formatTime(expiresIn)}
                        </span>
                    </div>
                </div>
                <div class="download-actions">
                    <a href="/download/${file.filename}" class="btn btn-small" download>
                        <i class="fas fa-download"></i>
                    </a>
                </div>
            </div>
        `;
    }

    async cleanupExpired() {
        if (!confirm('Limpar arquivos expirados?')) return;
        
        try {
            const response = await fetch('/api/cleanup', { method: 'POST' });
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(data.message, 'success');
                this.refreshDownloads();
            }
        } catch (error) {
            this.showNotification('Erro na limpeza', 'error');
        }
    }

    async showStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            if (data.error) {
                this.showNotification('Erro ao obter estatísticas', 'error');
                return;
            }
            
            this.displayStats(data);
        } catch (error) {
            console.error('Erro nas estatísticas:', error);
        }
    }

    displayStats(stats) {
        const { statsContent, stats: statsModal } = this.elements.modals;
        
        if (!statsContent) return;
        
        statsContent.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${stats.total_files || 0}</div>
                    <div class="stat-label">Arquivos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.total_size_mb || 0} MB</div>
                    <div class="stat-label">Espaço usado</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.active_downloads || 0}</div>
                    <div class="stat-label">Downloads ativos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.free_space_mb || 0} MB</div>
                    <div class="stat-label">Espaço livre</div>
                </div>
            </div>
            <div class="stats-info">
                <p><i class="fas fa-clock"></i> Arquivos expiram após: ${stats.max_file_age_hours || 1} hora(s)</p>
                <p><i class="fas fa-users"></i> Sessões ativas: ${stats.active_sessions || 0}</p>
            </div>
        `;
        
        this.showElement(statsModal);
    }

    clearLogs() {
        const { logOutput } = this.elements.progress;
        if (logOutput && confirm('Limpar todos os logs?')) {
            logOutput.innerHTML = '';
        }
    }

    togglePause() {
        // Implementação futura
        this.showNotification('Funcionalidade em desenvolvimento', 'info');
    }

    cancelDownload() {
        if (!this.state.isDownloading) return;
        
        if (confirm('Cancelar este download?')) {
            this.stopPolling();
            this.state.isDownloading = false;
            this.hideElement(this.elements.cards.progress);
            this.addLog('Download cancelado', 'warning');
        }
    }

    openDownloadsFolder() {
        window.open('/downloads', '_blank');
    }

    downloadCurrentFile() {
        if (this.state.currentDownloadUrl) {
            window.open(this.state.currentDownloadUrl, '_blank');
        }
    }

    disableButton(button, text) {
        if (!button) return;
        
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
        button.dataset.originalText = button.textContent;
    }

    enableButton(button, text) {
        if (!button) return;
        
        button.disabled = false;
        button.innerHTML = `<i class="fas fa-download"></i> ${text}`;
    }

    // ========== FORMATADORES ==========
    formatDuration(seconds) {
        if (!seconds) return '--:--';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    formatNumber(num) {
        if (!num) return '0';
        
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        
        return num.toString();
    }

    formatTime(minutes) {
        if (minutes <= 0) return 'Expirado';
        if (minutes < 60) return `${minutes} min`;
        
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        
        return mins === 0 ? `${hours}h` : `${hours}h ${mins}min`;
    }
}

// ========== INICIALIZAÇÃO ==========
let app = null;

document.addEventListener('DOMContentLoaded', () => {
    try {
        app = new YouTubeDownloader();
        window.downloader = app; // Para debugging
        
        console.log('🚀 Aplicação carregada com sucesso!');
    } catch (error) {
        console.error('❌ Erro ao inicializar:', error);
        alert('Erro ao carregar a aplicação. Recarregue a página.');
    }
});

// Utilitários globais (opcional)
window.showSuccessConfetti = () => {
    if (window.animations && window.animations.createConfetti) {
        window.animations.createConfetti();
    }
};