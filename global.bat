@echo off
:: ===============================================
:: Script completo para criar estrutura Flask
:: ===============================================

:: Criação das pastas
mkdir templates
mkdir static
mkdir static\css
mkdir static\js

:: Criação do index.html
echo ^<!DOCTYPE html^> > templates\index.html
echo ^<html lang="pt-br"^> >> templates\index.html
echo ^<head^> >> templates\index.html
echo     ^<meta charset="UTF-8"^> >> templates\index.html
echo     ^<meta name="viewport" content="width=device-width, initial-scale=1.0"^> >> templates\index.html
echo     ^<title^>Flask App^</title^> >> templates\index.html
echo     ^<link rel="stylesheet" href="^^{{ url_for('static', filename='css/style.css') ^^}}"^> >> templates\index.html
echo ^</head^> >> templates\index.html
echo ^<body^> >> templates\index.html
echo     ^<h1^>Aplicação Flask pronta!^</h1^> >> templates\index.html
echo     ^<p^>Este arquivo foi criado automaticamente.^</p^> >> templates\index.html
echo     ^<script src="^^{{ url_for('static', filename='js/script.js') ^^}}"^>^</script^> >> templates\index.html
echo ^</body^> >> templates\index.html
echo ^</html^> >> templates\index.html

:: Criação do style.css
echo body { > static\css\style.css
echo     font-family: Arial, sans-serif; >> static\css\style.css
echo     background-color: #121212; >> static\css\style.css
echo     color: #fff; >> static\css\style.css
echo     text-align: center; >> static\css\style.css
echo     margin-top: 100px; >> static\css\style.css
echo } >> static\css\style.css

:: Criação do script.js (linha por linha)
echo document.addEventListener('DOMContentLoaded', function() { > static\js\script.js
echo     console.log('Script carregado com sucesso!'); >> static\js\script.js
echo }); >> static\js\script.js

:: Criação do app.py
echo from flask import Flask, render_template > app.py
echo. >> app.py
echo app = Flask(__name__) >> app.py
echo. >> app.py
echo @app.route("/") >> app.py
echo def home(): >> app.py
echo     return render_template("index.html") >> app.py
echo. >> app.py
echo if __name__ == "__main__": >> app.py
echo     app.run(debug=True) >> app.py

:: Mensagem final
echo.
echo ======================================
echo ✅ Estrutura Flask completa criada com sucesso!
echo ======================================
pause
