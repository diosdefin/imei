# universal_django_analyzer.py
import os
import glob

def discover_django_structure():
    """Автоматически обнаруживает структуру Django проекта"""
    structure_lines = ["АРХИТЕКТУРА DJANGO ПРОЕКТА:", "=" * 50]
    
    # Ищем manage.py для определения корня проекта
    manage_py = glob.glob('manage.py')
    if not manage_py:
        structure_lines.append("❌ Не найден manage.py - возможно, это не Django проект")
        return "\n".join(structure_lines)
    
    structure_lines.append("📁 КОРЕНЬ ПРОЕКТА:")
    
    # Файлы в корне проекта
    root_files = [
        'manage.py', 'requirements.txt', 'requirements-dev.txt', 
        'Pipfile', 'pyproject.toml', 'setup.py', 'env.example', '.env',
        'Dockerfile', 'docker-compose.yml', 'README.md', '.gitignore',
        '.python-version', 'runtime.txt', 'Procfile'
    ]
    
    for file in root_files:
        if glob.glob(file):
            structure_lines.append(f"├── {file}")
    
    # Ищем папки с приложениями (те, что содержат apps.py)
    app_folders = []
    for folder in glob.glob('*/'):
        if os.path.isdir(folder):
            apps_py = glob.glob(os.path.join(folder, 'apps.py'))
            if apps_py:
                app_folders.append(folder.rstrip('/'))
    
    # Ищем папку config/settings (типичная структура)
    config_folders = []
    for folder in glob.glob('*/'):
        folder_name = folder.rstrip('/')
        settings_py = glob.glob(os.path.join(folder, 'settings.py'))
        urls_py = glob.glob(os.path.join(folder, 'urls.py'))
        wsgi_py = glob.glob(os.path.join(folder, 'wsgi.py'))
        asgi_py = glob.glob(os.path.join(folder, 'asgi.py'))
        if settings_py or urls_py or wsgi_py or asgi_py:
            config_folders.append(folder_name)
    
    # Выводим конфигурационные папки
    if config_folders:
        structure_lines.append("\n📁 КОНФИГУРАЦИЯ:")
        for config_folder in sorted(config_folders):
            structure_lines.append(f"├── {config_folder}/")
            config_files = glob.glob(f"{config_folder}/*.py")
            for file_path in sorted(config_files):
                file_name = os.path.basename(file_path)
                structure_lines.append(f"│   ├── {file_name}")
    
    # Выводим приложения
    if app_folders:
        structure_lines.append("\n📁 ПРИЛОЖЕНИЯ:")
        for app_folder in sorted(app_folders):
            structure_lines.append(f"├── {app_folder}/")
            
            # Стандартные Django файлы в приложении
            django_files = []
            patterns = [
                'models.py', 'views.py', 'urls.py', 'admin.py', 
                'apps.py', 'serializers.py', 'forms.py', 'tests.py',
                'signals.py', 'managers.py', 'constants.py', 'tasks.py',
                'utils.py', 'helpers.py', 'decorators.py', 'middleware.py',
                'factories.py', 'context_processors.py'
            ]
            
            for pattern in patterns:
                found_files = glob.glob(f"{app_folder}/{pattern}")
                django_files.extend(found_files)
            
            # Добавляем папки migrations, templates, static если они есть
            migrations_dir = glob.glob(f"{app_folder}/migrations")
            templates_dir = glob.glob(f"{app_folder}/templates")
            static_dir = glob.glob(f"{app_folder}/static")
            
            for file_path in sorted(django_files):
                file_name = os.path.basename(file_path)
                structure_lines.append(f"│   ├── {file_name}")
            
            if migrations_dir:
                structure_lines.append("│   ├── migrations/")
                migration_files = glob.glob(f"{app_folder}/migrations/*.py")
                for mig_file in sorted(migration_files):
                    mig_name = os.path.basename(mig_file)
                    structure_lines.append(f"│   │   ├── {mig_name}")
            
            if templates_dir:
                structure_lines.append("│   ├── templates/")
                template_files = []
                for ext in ['*.html', '*.txt', '*.xml', '*.json']:
                    template_files.extend(glob.glob(f"{app_folder}/templates/**/{ext}", recursive=True))
                
                # Показываем полную структуру templates
                for tpl_file in sorted(template_files):
                    rel_path = os.path.relpath(tpl_file, f"{app_folder}/templates")
                    structure_lines.append(f"│   │   ├── {rel_path}")
            
            if static_dir:
                structure_lines.append("│   ├── static/")
                static_files = []
                for ext in ['*.css', '*.js', '*.png', '*.jpg', '*.jpeg', '*.gif', '*.svg', '*.ico']:
                    static_files.extend(glob.glob(f"{app_folder}/static/**/{ext}", recursive=True))
                
                for static_file in sorted(static_files)[:20]:  # Показываем первые 20 для читаемости
                    rel_path = os.path.relpath(static_file, f"{app_folder}/static")
                    structure_lines.append(f"│   │   ├── {rel_path}")
                
                if len(static_files) > 20:
                    structure_lines.append(f"│   │   └── ... и еще {len(static_files) - 20} статических файлов")
    
    # Дополнительные папки
    extra_folders = ['static', 'media', 'templates', 'docs', 'scripts', 'locale', 'tests', 'fixtures']
    found_extra = []
    for folder in extra_folders:
        if glob.glob(folder):
            found_extra.append(folder)
    
    if found_extra:
        structure_lines.append("\n📁 ДОПОЛНИТЕЛЬНЫЕ ПАПКИ:")
        for folder in sorted(found_extra):
            structure_lines.append(f"├── {folder}/")
            
            # Показываем содержимое корневых templates
            if folder == 'templates':
                template_files = []
                for ext in ['*.html', '*.txt', '*.xml']:
                    template_files.extend(glob.glob(f"templates/**/{ext}", recursive=True))
                
                for tpl_file in sorted(template_files):
                    rel_path = os.path.relpath(tpl_file, "templates")
                    structure_lines.append(f"│   ├── {rel_path}")
            
            # Показываем содержимое корневых static
            elif folder == 'static':
                static_files = []
                for ext in ['*.css', '*.js']:
                    static_files.extend(glob.glob(f"static/**/{ext}", recursive=True))
                
                for static_file in sorted(static_files)[:15]:
                    rel_path = os.path.relpath(static_file, "static")
                    structure_lines.append(f"│   ├── {rel_path}")
                
                if len(static_files) > 15:
                    structure_lines.append(f"│   └── ... и еще {len(static_files) - 15} файлов")
    
    return "\n".join(structure_lines)

def find_django_files():
    """Находит все важные Django файлы в проекте"""
    target_patterns = [
        'manage.py',
        'requirements*.txt',
        'Pipfile',
        'pyproject.toml',
        'setup.py',
        '*/settings.py',
        '*/urls.py', 
        '*/celery.py',
        '*/models.py',
        '*/views.py', 
        '*/admin.py',
        '*/apps.py',
        '*/serializers.py',
        '*/tasks.py',
        '*/forms.py',
        '*/signals.py',
        '*/utils.py',
        '*/middleware.py',
        '*/wsgi.py',
        '*/asgi.py',
        '*/context_processors.py'
    ]
    
    found_files = []
    for pattern in target_patterns:
        found_files.extend(glob.glob(pattern, recursive=True))
    
    # Убираем дубликаты и сортируем
    return sorted(list(set(found_files)))

def find_template_files():
    """Находит все HTML шаблоны в проекте"""
    template_patterns = [
        'templates/**/*.html',
        '*/templates/**/*.html',
        '**/templates/**/*.html',
        'templates/**/*.txt',
        '*/templates/**/*.txt'
    ]
    
    template_files = []
    for pattern in template_patterns:
        template_files.extend(glob.glob(pattern, recursive=True))
    
    return sorted(list(set(template_files)))

def find_static_files():
    """Находит основные статические файлы"""
    static_patterns = [
        'static/**/*.css',
        '*/static/**/*.css',
        'static/**/*.js', 
        '*/static/**/*.js',
        'static/**/style*.css',
        'static/**/main*.css',
        'static/**/script*.js',
        'static/**/main*.js'
    ]
    
    static_files = []
    for pattern in static_patterns:
        static_files.extend(glob.glob(pattern, recursive=True))
    
    return sorted(list(set(static_files)))

def read_file_content(file_path):
    """Читает полное содержимое файла без ограничений"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='cp1251') as f:
                return f.read()
        except:
            return f"❌ Не удалось прочитать файл {file_path} (проблемы с кодировкой)"
    except Exception as e:
        return f"❌ Ошибка чтения {file_path}: {e}"

def create_universal_dump():
    """Создает полный дамп Django проекта без ограничений"""
    
    with open('django_complete_analysis.txt', 'w', encoding='utf-8') as f:
        # 1. Структура проекта
        f.write("ПОЛНЫЙ АНАЛИЗ DJANGO ПРОЕКТА\n")
        f.write("=" * 60 + "\n\n")
        
        structure = discover_django_structure()
        f.write(structure)
        f.write("\n\n" + "=" * 60 + "\n\n")
        
        # 2. Содержимое Python файлов
        f.write("СОДЕРЖИМОЕ PYTHON ФАЙЛОВ:\n")
        f.write("=" * 60 + "\n\n")
        
        django_files = find_django_files()
        files_processed = 0
        
        for file_path in django_files:
            if not os.path.isfile(file_path):
                continue
                
            content = read_file_content(file_path)
            
            # Пропускаем полностью пустые файлы
            if not content.strip():
                continue
            
            f.write(f"🚀 ФАЙЛ: {file_path}\n")
            f.write("-" * 40 + "\n")
            f.write(content)
            f.write("\n\n" + "═" * 60 + "\n\n")
            files_processed += 1
        
        # 3. Содержимое HTML шаблонов
        template_files = find_template_files()
        if template_files:
            f.write("\n🎨 HTML ШАБЛОНЫ:\n")
            f.write("=" * 60 + "\n\n")
            
            for template_path in template_files:
                if not os.path.isfile(template_path):
                    continue
                    
                content = read_file_content(template_path)
                
                f.write(f"📄 ШАБЛОН: {template_path}\n")
                f.write("-" * 40 + "\n")
                f.write(content)
                f.write("\n\n" + "─" * 60 + "\n\n")
                files_processed += 1
        
        # 4. Содержимое основных CSS/JS файлов
        static_files = find_static_files()
        if static_files:
            f.write("\n🎨 ОСНОВНЫЕ СТАТИЧЕСКИЕ ФАЙЛЫ:\n")
            f.write("=" * 60 + "\n\n")
            
            for static_path in static_files:
                if not os.path.isfile(static_path):
                    continue
                    
                content = read_file_content(static_path)
                
                f.write(f"📁 СТАТИЧЕСКИЙ ФАЙЛ: {static_path}\n")
                f.write("-" * 40 + "\n")
                f.write(content)
                f.write("\n\n" + "─" * 60 + "\n\n")
                files_processed += 1
        
        # 5. Статистика
        f.write(f"📊 ПОЛНАЯ СТАТИСТИКА ПРОЕКТА:\n")
        f.write("-" * 40 + "\n")
        f.write(f"• Всего обработано файлов: {files_processed}\n")
        f.write(f"• Python файлов: {len(django_files)}\n")
        f.write(f"• HTML шаблонов: {len(template_files)}\n")
        f.write(f"• Статических файлов (CSS/JS): {len(static_files)}\n")
        
        # Подсчет приложений
        app_folders = [f for f in glob.glob('*/') if glob.glob(os.path.join(f, 'apps.py'))]
        f.write(f"• Приложений Django: {len(app_folders)}\n")
        
        if app_folders:
            f.write(f"• Список приложений: {', '.join(sorted([app.rstrip('/') for app in app_folders]))}\n")
        
        # Детальная статистика
        model_files = glob.glob('**/models.py', recursive=True)
        view_files = glob.glob('**/views.py', recursive=True)
        url_files = glob.glob('**/urls.py', recursive=True)
        migration_files = glob.glob('**/migrations/*.py', recursive=True)
        
        f.write(f"• Файлов models.py: {len(model_files)}\n")
        f.write(f"• Файлов views.py: {len(view_files)}\n")
        f.write(f"• Файлов urls.py: {len(url_files)}\n")
        f.write(f"• Файлов миграций: {len(migration_files)}\n")
        
        # Общий размер проекта
        total_size = 0
        for dirpath, dirnames, filenames in os.walk('.'):
            for filename in filenames:
                if any(ignore in dirpath for ignore in ['.git', '__pycache__', '.venv', 'venv']):
                    continue
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        
        f.write(f"• Общий размер проекта: {total_size / 1024 / 1024:.2f} MB\n")
    
    print(f"✅ Полный анализ завершен! Результат сохранен в django_complete_analysis.txt")
    print(f"📁 Обработано {files_processed} файлов")
    print(f"📊 Статистика: {len(django_files)} Python, {len(template_files)} HTML, {len(static_files)} CSS/JS")

if __name__ == "__main__":
    print("🔍 Начинаю полный анализ структуры Django проекта...")
    create_universal_dump()