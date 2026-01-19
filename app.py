from flask import Flask, render_template, request, jsonify, send_file, session
import subprocess
import os
import sys
import uuid
import threading
import json
import re
import logging
from datetime import datetime, timedelta
import time
import shutil
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'amazed-secret-key-v1.3'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB limite
app.config['MAX_FILE_AGE_HOURS'] = 0.25  # Arquivos expiram em 1 hora
app.config['CLEANUP_INTERVAL_MINUTES'] = 5  # Limpar a cada 5 minutos

# Configurações de caminhos
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

download_path = os.path.join(base_path, "downloads")
ytdlp_path = os.path.join(base_path, "yt-dlp.exe")
ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
ffprobe_path = os.path.join(base_path, "ffprobe.exe")

# Criar pastas necessárias
if not os.path.exists(download_path):
    os.makedirs(download_path)

# Armazenamento de status de download por sessão
download_sessions = {}  # {session_id: {downloads: [], status: {}}}
_status_lock = threading.Lock()

class DownloadManager:
    """Gerencia downloads por usuário/sessão"""
    
    @staticmethod
    def sanitize_filename(filename):
        """Remove caracteres inválidos para nome de arquivo"""
        return re.sub(r'[<>:"/\\|?*]', '', filename)
    
    @staticmethod
    def get_user_folder(session_id):
        """Cria pasta específica para cada usuário"""
        user_folder = os.path.join(download_path, f"user_{session_id}")
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        return user_folder
    
    @staticmethod
    def generate_filename(original_name, session_id, file_type):
        """Gera nome de arquivo único com extensão correta"""
        timestamp = int(time.time())
        short_id = session_id[:8]
        
        # Determinar extensão baseada no tipo
        if file_type == 'audio':
            ext = '.mp3'
        elif file_type == 'audio_best':
            ext = '.m4a'
        else:  # video
            ext = '.mp4'
        
        safe_name = DownloadManager.sanitize_filename(original_name)[:50]
        return f"{safe_name}_{timestamp}_{short_id}{ext}"
    
    @staticmethod
    def get_video_info(url):
        """Obtém informações do vídeo usando yt-dlp"""
        try:
            cmd = [
                ytdlp_path,
                "--skip-download",
                "--dump-json",
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, shell=False, timeout=30)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                return {
                    'success': True,
                    'title': info.get('title', 'Sem título'),
                    'author': info.get('uploader', 'Desconhecido'),
                    'duration': info.get('duration', 0),
                    'views': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', '')
                }
            else:
                return {
                    'success': False,
                    'error': f"Erro ao obter informações: {result.stderr[:200]}"
                }
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Timeout ao obter informações do vídeo'}
        except Exception as e:
            logger.error(f"Erro ao obter info do vídeo: {str(e)}")
            return {'success': False, 'error': f"Erro: {str(e)}"}
def cleanup_old_files():
    """Remove arquivos antigos de TODOS os usuários"""
    try:
        max_age = timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
        now = datetime.now()
        deleted_count = 0
        
        # Limpar pastas de usuários
        for item in os.listdir(download_path):
            item_path = os.path.join(download_path, item)
            
            if os.path.isdir(item_path) and item.startswith('user_'):
                # VERIFICAR PRIMEIRO OS ARQUIVOS DENTRO DA PASTA
                files_deleted_in_folder = 0
                for filename in os.listdir(item_path):
                    filepath = os.path.join(item_path, filename)
                    if os.path.isfile(filepath):
                        try:
                            file_age = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if now - file_age > max_age:
                                os.remove(filepath)
                                deleted_count += 1
                                files_deleted_in_folder += 1
                                logger.info(f"Arquivo expirado removido: {filename}")
                        except Exception as e:
                            logger.error(f"Erro ao remover arquivo {filename}: {e}")
                
                # DEPOIS verificar se a pasta está vazia ou muito antiga
                try:
                    folder_age = datetime.fromtimestamp(os.path.getmtime(item_path))
                    
                    # Se pasta estiver vazia OU muito antiga, remover
                    if (len(os.listdir(item_path)) == 0) or (now - folder_age > max_age * 2):
                        shutil.rmtree(item_path, ignore_errors=True)
                        if len(os.listdir(item_path)) == 0:
                            logger.info(f"Pasta vazia removida: {item}")
                        else:
                            logger.info(f"Pasta expirada removida: {item} (tinha {files_deleted_in_folder} arquivos expirados)")
                except:
                    pass
            
            elif os.path.isfile(item_path):
                # Remover arquivos soltos (antigo sistema)
                try:
                    file_age = datetime.fromtimestamp(os.path.getmtime(item_path))
                    if now - file_age > max_age:
                        os.remove(item_path)
                        deleted_count += 1
                        logger.info(f"Arquivo solto expirado removido: {item}")
                except:
                    pass
        
        if deleted_count > 0:
            logger.info(f"Limpeza automática: {deleted_count} item(s) removido(s)")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Erro na limpeza automática: {e}")
        return 0

def schedule_cleanup():
    """Agenda limpezas periódicas"""
    def cleanup_task():
        while True:
            time.sleep(app.config['CLEANUP_INTERVAL_MINUTES'] * 60)
            cleanup_old_files()
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    logger.info("Limpeza automática agendada")

def get_or_create_session():
    """Obtém ou cria uma sessão única para o usuário"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session.permanent = True
    
    session_id = session['session_id']
    
    # Inicializar sessão se não existir
    with _status_lock:
        if session_id not in download_sessions:
            download_sessions[session_id] = {
                'downloads': [],  # Lista de downloads do usuário
                'status': {},     # Status dos downloads ativos
                'created': datetime.now().isoformat()
            }
    
    return session_id

def download_task(session_id, download_id, url, option, custom_filename=None):
    """Executa o download em uma thread separada"""
    try:
        # Obter informações do vídeo primeiro
        video_info = DownloadManager.get_video_info(url)
        if not video_info['success']:
            with _status_lock:
                if session_id in download_sessions:
                    download_sessions[session_id]['status'][download_id] = {
                        'status': 'error',
                        'message': f"Erro ao obter informações: {video_info['error']}",
                        'progress': 0
                    }
            return False
        
        video_title = video_info['title']
        
        # Criar pasta do usuário
        user_folder = DownloadManager.get_user_folder(session_id)
        
        # Determinar tipo de arquivo e extensão
        if option == "Audio Standard MP3":
            file_type = 'audio'
            output_ext = '.mp3'
        elif option == "Audio Best Quality":
            file_type = 'audio_best'
            output_ext = '.m4a'
        else:  # Video options
            file_type = 'video'
            output_ext = '.mp4'
        
        # Gerar nome do arquivo final
        if custom_filename:
            base_name = DownloadManager.sanitize_filename(custom_filename)
        else:
            base_name = DownloadManager.sanitize_filename(video_title)
        
        final_filename = DownloadManager.generate_filename(base_name, session_id, file_type)
        final_filepath = os.path.join(user_folder, final_filename)
        
        # Criar template de saída temporário
        temp_filename = f"temp_{download_id}{output_ext}"
        temp_filepath = os.path.join(user_folder, temp_filename)
        output_template = temp_filepath
        
        # Base do comando
        cmd_base = [ytdlp_path, "--ffmpeg-location", base_path, "-o", output_template]
        
        # Configurar comandos baseados na opção selecionada
        if option == "Audio Standard MP3":
            cmd = cmd_base + [
                "-x", "--audio-format", "mp3", 
                "--embed-metadata", "--embed-thumbnail", "--embed-chapters",
                "--sleep-interval", "5", "--max-sleep-interval", "15",
                url
            ]
            
        elif option == "Audio Best Quality":
            cmd = cmd_base + [
                "-x", "--audio-format", "m4a",
                "--audio-quality", "0",
                "--embed-metadata", "--embed-thumbnail", "--embed-chapters",
                "--sleep-interval", "5", "--max-sleep-interval", "15",
                url
            ]
            
        elif option == "Video MP4 Full HD":
            cmd = cmd_base + [
                "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", 
                "--embed-metadata", "--embed-thumbnail", "--embed-chapters",
                "--embed-subs", "--sub-langs", "es.*,en",
                "--sleep-interval", "5", "--max-sleep-interval", "15",
                url
            ]
            
        else:  # "Video Best Quality"
            cmd = cmd_base + [
                "--embed-metadata", "--embed-thumbnail", "--embed-chapters", 
                "--embed-subs", "--sub-langs", "es.*,en",
                "--sleep-interval", "5", "--max-sleep-interval", "15",
                url
            ]
        
        # Atualizar status (thread-safe)
        with _status_lock:
            if session_id in download_sessions:
                download_sessions[session_id]['status'][download_id] = {
                    'status': 'downloading',
                    'message': 'Iniciando download...',
                    'progress': 0,
                    'logs': [],
                    'start_time': datetime.now().isoformat(),
                    'filename': final_filename,
                    'original_name': base_name
                }
        
        # Executar processo
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            shell=False
        )
        
        # Ler saída
        output_lines = []
        for line in process.stdout:
            line = line.strip()
            output_lines.append(line)
            
            with _status_lock:
                if session_id in download_sessions and download_id in download_sessions[session_id]['status']:
                    download_sessions[session_id]['status'][download_id]['logs'].append(line)
                    if len(download_sessions[session_id]['status'][download_id]['logs']) > 100:
                        download_sessions[session_id]['status'][download_id]['logs'].pop(0)
            
            # Detectar progresso
            if '[download]' in line and '%' in line:
                percent_match = re.search(r'(\d+\.?\d*)%', line)
                if percent_match:
                    progress = float(percent_match.group(1))
                    with _status_lock:
                        if session_id in download_sessions and download_id in download_sessions[session_id]['status']:
                            download_sessions[session_id]['status'][download_id]['progress'] = progress
                            download_sessions[session_id]['status'][download_id]['message'] = line
        
        # Aguardar término
        process.wait()
        
        if process.returncode == 0 and os.path.exists(temp_filepath):
            # Renomear arquivo temporário para nome final
            os.rename(temp_filepath, final_filepath)
            
            # Registrar download concluído
            file_size = os.path.getsize(final_filepath)
            
            with _status_lock:
                if session_id in download_sessions:
                    # Atualizar status
                    download_sessions[session_id]['status'][download_id] = {
                        'status': 'completed',
                        'message': 'Download concluído com sucesso!',
                        'progress': 100,
                        'filename': final_filename,
                        'filepath': final_filepath,
                        'original_name': base_name,
                        'file_size': file_size,
                        'complete_time': datetime.now().isoformat()
                    }
                    
                    # Adicionar à lista de downloads do usuário
                    download_info = {
                        'id': download_id,
                        'filename': final_filename,
                        'original_name': base_name,
                        'file_size': file_size,
                        'created': datetime.now().isoformat(),
                        'expires_at': (datetime.now() + timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])).isoformat()
                    }
                    
                    # Manter apenas os últimos 20 downloads
                    download_sessions[session_id]['downloads'].append(download_info)
                    if len(download_sessions[session_id]['downloads']) > 20:
                        download_sessions[session_id]['downloads'] = download_sessions[session_id]['downloads'][-20:]
            
            return True
        else:
            # Limpar arquivo temporário se existir
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except:
                    pass
        
        # Se chegou aqui, algo deu errado
        with _status_lock:
            if session_id in download_sessions and download_id in download_sessions[session_id]['status']:
                download_sessions[session_id]['status'][download_id] = {
                    'status': 'error',
                    'message': 'Erro durante o download',
                    'progress': 0,
                    'error_output': '\n'.join(output_lines[-10:])
                }
        return False
        
    except Exception as e:
        logger.error(f"Erro no download: {str(e)}")
        with _status_lock:
            if session_id in download_sessions and download_id in download_sessions[session_id]['status']:
                download_sessions[session_id]['status'][download_id] = {
                    'status': 'error',
                    'message': f"Erro: {str(e)}",
                    'progress': 0
                }
        return False

# ========== ROTAS DA APLICAÇÃO ==========

@app.route('/')
def index():
    """Página inicial - Cria sessão única para cada usuário"""
    session_id = get_or_create_session()
    logger.info(f"Novo usuário conectado: {session_id[:8]}")
    return render_template('index.html')

@app.route('/api/get_info', methods=['POST'])
def api_get_info():
    """API para obter informações do vídeo"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        info = DownloadManager.get_video_info(url)
        
        if info['success']:
            return jsonify({
                'success': True,
                'title': info['title'],
                'author': info['author'],
                'duration': info['duration'],
                'views': info['views'],
                'thumbnail': info['thumbnail']
            })
        else:
            return jsonify({'error': info['error']}), 500
        
    except Exception as e:
        logger.error(f"Erro na API get_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """API para iniciar download"""
    try:
        # Obter sessão do usuário
        session_id = get_or_create_session()
        
        data = request.json
        url = data.get('url')
        option = data.get('option', 'Video Best Quality')
        custom_filename = data.get('custom_filename')
        
        if not url:
            return jsonify({'error': 'URL não fornecida'}), 400
        
        # Gerar ID único para este download
        download_id = str(uuid.uuid4())
        
        # Verificar se já tem muitos downloads ativos
        with _status_lock:
            if session_id in download_sessions:
                active_downloads = sum(
                    1 for status in download_sessions[session_id]['status'].values() 
                    if status.get('status') == 'downloading'
                )
            else:
                active_downloads = 0
        
        if active_downloads >= 3:
            return jsonify({
                'success': False,
                'error': 'Muitos downloads em andamento. Tente novamente em alguns instantes.'
            }), 429
        
        # Iniciar thread de download
        thread = threading.Thread(
            target=download_task,
            args=(session_id, download_id, url, option, custom_filename),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'download_id': download_id,
            'message': 'Download iniciado em segundo plano'
        })
        
    except Exception as e:
        logger.error(f"Erro na API download: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<download_id>')
def api_status(download_id):
    """API para verificar status do download"""
    try:
        session_id = get_or_create_session()
        
        with _status_lock:
            if (session_id in download_sessions and 
                download_id in download_sessions[session_id]['status']):
                
                status = download_sessions[session_id]['status'][download_id].copy()
                
                # Adicionar informações de expiração se disponível
                if status.get('status') == 'completed':
                    expires_at = datetime.now() + timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
                    time_left = expires_at - datetime.now()
                    minutes_left = max(0, int(time_left.total_seconds() / 60))
                    status['expires_in_minutes'] = minutes_left
                
                # Limitar logs retornados
                if 'logs' in status and len(status['logs']) > 20:
                    status['logs'] = status['logs'][-20:]
                
                return jsonify(status)
            else:
                return jsonify({
                    'status': 'unknown',
                    'message': 'Download não encontrado',
                    'progress': 0
                })
        
    except Exception as e:
        logger.error(f"Erro ao verificar status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Serve o arquivo para download (apenas para o usuário da sessão)"""
    try:
        session_id = get_or_create_session()
        user_folder = DownloadManager.get_user_folder(session_id)
        filepath = os.path.join(user_folder, filename)
        
        if not os.path.exists(filepath):
            return "Arquivo não encontrado ou expirado", 404
        
        # Verificar se o arquivo pertence a este usuário
        if not filepath.startswith(user_folder):
            return "Acesso negado", 403
        
        # Verificar se o arquivo é muito antigo
        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(filepath))
        max_age = timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
        
        if file_age > max_age:
            try:
                os.remove(filepath)
            except:
                pass
            return "Arquivo expirado", 410
        
        # Determinar mimetype
        if filename.endswith('.mp3'):
            mimetype = 'audio/mpeg'
        elif filename.endswith('.m4a'):
            mimetype = 'audio/mp4'
        elif filename.endswith('.mp4'):
            mimetype = 'video/mp4'
        else:
            mimetype = 'application/octet-stream'
        
        # Procurar nome original
        original_name = None
        with _status_lock:
            if session_id in download_sessions:
                for download in download_sessions[session_id]['downloads']:
                    if download['filename'] == filename:
                        original_name = download['original_name']
                        break
        
        download_name = f"{original_name}{os.path.splitext(filename)[1]}" if original_name else filename
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=download_name,
            mimetype=mimetype
        )
        
    except Exception as e:
        logger.error(f"Erro ao servir arquivo: {str(e)}")
        return "Erro ao processar download", 500

@app.route('/api/my_downloads')
def api_my_downloads():
    """Lista APENAS os downloads do usuário atual"""
    try:
        session_id = get_or_create_session()
        
        files = []
        user_folder = DownloadManager.get_user_folder(session_id)
        max_age = timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
        now = datetime.now()
        
        # Listar arquivos da pasta do usuário
        if os.path.exists(user_folder):
            for filename in os.listdir(user_folder):
                filepath = os.path.join(user_folder, filename)
                if os.path.isfile(filepath):
                    file_age = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    # Verificar se o arquivo ainda é válido
                    if now - file_age > max_age:
                        continue
                    
                    stats = os.stat(filepath)
                    expires_at = file_age + max_age
                    expires_in = int((expires_at - now).total_seconds() / 60)
                    
                    # Procurar nome original
                    original_name = None
                    with _status_lock:
                        if session_id in download_sessions:
                            for download in download_sessions[session_id]['downloads']:
                                if download['filename'] == filename:
                                    original_name = download['original_name']
                                    break
                    
                    files.append({
                        'filename': filename,
                        'original_name': original_name,
                        'size': stats.st_size,
                        'size_mb': round(stats.st_size / (1024 * 1024), 2),
                        'modified': file_age.isoformat(),
                        'expires_in_minutes': max(0, expires_in)
                    })
        
        # Ordenar por data de modificação (mais recente primeiro)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'files': files})
        
    except Exception as e:
        logger.error(f"Erro ao listar downloads: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    """Limpa arquivos antigos do usuário atual"""
    try:
        session_id = get_or_create_session()
        user_folder = DownloadManager.get_user_folder(session_id)
        
        deleted_count = 0
        max_age = timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
        now = datetime.now()
        
        if os.path.exists(user_folder):
            for filename in os.listdir(user_folder):
                filepath = os.path.join(user_folder, filename)
                if os.path.isfile(filepath):
                    file_age = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if now - file_age > max_age:
                        try:
                            os.remove(filepath)
                            deleted_count += 1
                        except:
                            pass
        
        # Limpar sessões antigas
        with _status_lock:
            sessions_to_remove = []
            for sess_id, sess_data in download_sessions.items():
                created = datetime.fromisoformat(sess_data['created'])
                if now - created > max_age:
                    sessions_to_remove.append(sess_id)
            
            for sess_id in sessions_to_remove:
                del download_sessions[sess_id]
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} arquivo(s) expirado(s) removido(s)',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Erro na limpeza manual: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """Retorna estatísticas do sistema"""
    try:
        # Contar arquivos de todos os usuários
        total_files = 0
        total_size = 0
        active_sessions = 0
        
        max_age = timedelta(hours=app.config['MAX_FILE_AGE_HOURS'])
        now = datetime.now()
        
        # Contar arquivos válidos
        for item in os.listdir(download_path):
            item_path = os.path.join(download_path, item)
            
            if os.path.isdir(item_path) and item.startswith('user_'):
                # Verificar se a pasta não está expirada
                try:
                    folder_age = datetime.fromtimestamp(os.path.getmtime(item_path))
                    if now - folder_age <= max_age:
                        active_sessions += 1
                except:
                    pass
                
                for filename in os.listdir(item_path):
                    filepath = os.path.join(item_path, filename)
                    if os.path.isfile(filepath):
                        try:
                            file_age = datetime.fromtimestamp(os.path.getmtime(filepath))
                            if now - file_age <= max_age:
                                total_files += 1
                                total_size += os.path.getsize(filepath)
                        except:
                            pass
        
        with _status_lock:
            active_downloads = sum(
                1 for sess_data in download_sessions.values()
                for status in sess_data['status'].values()
                if status.get('status') == 'downloading'
            )
        
        # Espaço livre
        if sys.platform == 'win32':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(download_path), 
                None, None, 
                ctypes.pointer(free_bytes)
            )
            free_space = free_bytes.value
        else:
            import shutil
            free_space = shutil.disk_usage(download_path).free
        
        return jsonify({
            'total_files': total_files,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'active_downloads': active_downloads,
            'active_sessions': active_sessions,
            'free_space_mb': round(free_space / (1024 * 1024), 2),
            'max_file_age_hours': app.config['MAX_FILE_AGE_HOURS']
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}")
        return jsonify({'error': str(e)}), 500

def check_required_files():
    """Verifica se os arquivos necessários existem"""
    missing = []
    for file_path, name in [
        (ytdlp_path, "yt-dlp.exe"),
        (ffmpeg_path, "ffmpeg.exe"),
        (ffprobe_path, "ffprobe.exe")
    ]:
        if not os.path.exists(file_path):
            missing.append(name)
            logger.warning(f"Arquivo não encontrado: {name}")
    
    if missing:
        logger.warning(f"Arquivos ausentes: {', '.join(missing)}")
    
    return len(missing) == 0

# ========== INICIALIZAÇÃO ==========

if __name__ == '__main__':
    # Verificar arquivos necessários
    files_ok = check_required_files()
    
    if not files_ok:
        print("=" * 60)
        print("AVISO: Alguns arquivos necessários não foram encontrados!")
        print("Certifique-se de que yt-dlp.exe, ffmpeg.exe e ffprobe.exe")
        print("estejam na mesma pasta do app.py")
        print("=" * 60)
    else:
        print("✓ Todos os arquivos necessários encontrados")
    
    # Iniciar limpeza automática
    schedule_cleanup()
    
    print("=" * 60)
    print("Amazed YouTube Downloader Web v1.4")
    print("=" * 60)
    print("NOVO: Sistema multi-usuário com isolamento de sessões")
    print("✓ Cada usuário tem sua própria pasta de downloads")
    print("✓ Histórico NÃO é compartilhado entre usuários")
    print("✓ Arquivos temporários são automaticamente removidos")
    print("=" * 60)
    print(f"Pasta base: {download_path}")
    print(f"Arquivos expiram após: {app.config['MAX_FILE_AGE_HOURS']} hora(s)")
    print(f"Limpeza automática a cada: {app.config['CLEANUP_INTERVAL_MINUTES']} minuto(s)")
    print(f"Servidor rodando em: http://localhost:5000")
    print("=" * 60)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5003)
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    except Exception as e:
        print(f"Erro ao iniciar servidor: {e}")