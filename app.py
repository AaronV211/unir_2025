import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

app.secret_key = 'unirproyecto_seguro'

app.config['MYSQL_HOST'] = '45.195.229.16'
app.config['MYSQL_USER'] = 'adminremote'
app.config['MYSQL_PASSWORD'] = 'unir'
app.config['MYSQL_DB'] = 'unir'
app.config['MYSQL_CONNECT_TIMEOUT'] = 60 

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

mysql = MySQL(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_cursor():
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)

def ensure_follows_table(cursor):
    """Crea la tabla de seguimientos si aún no existe."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follows (
                id INT AUTO_INCREMENT PRIMARY KEY,
                follower_id INT NOT NULL,
                followed_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_follow (follower_id, followed_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cursor.connection.commit()
    except Exception as e:
        # Si falla no detenemos la app, solo lo registramos en consola
        print("No se pudo crear/verificar la tabla follows:", e)

@app.route('/')
def home():
    if 'login' in session:
        try:
            cursor = get_db_cursor()
            cursor.execute('''
                SELECT posts.*, usuarios.nombre, usuarios.foto_perfil 
                FROM posts 
                JOIN usuarios ON posts.user_id = usuarios.id 
                ORDER BY posts.fecha DESC
            ''')
            posts = cursor.fetchall()
            
            cursor.execute('SELECT * FROM usuarios WHERE id = %s', (session['userid'],))
            current_user_data = cursor.fetchone()
            
            cursor.close()
            return render_template('index.html', posts=posts, user=current_user_data)
        except Exception as e:
            print(f"Error en home: {e}")
            flash('Error de conexión con la base de datos. Se muestra versión sin conexión.', 'error')
            
            user_fallback = {
                'id': session.get('userid'),
                'nombre': session.get('username'),
                'foto_perfil': None,
                'email': 'Sin conexión'
            }
            return render_template('index.html', posts=[], user=user_fallback)
    
    return redirect(url_for('login'))

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    if 'login' not in session: return redirect(url_for('login'))
    
    resultados = []
    busqueda = ""
    current_user_data = None
    
    try:
        cursor = get_db_cursor()
        
        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (session['userid'],))
        current_user_data = cursor.fetchone()

        if request.method == 'POST':
            
            busqueda = request.form.get('busqueda', '').strip()
            
            if busqueda:
                query_string = "%" + busqueda + "%"
                
                cursor.execute('''
                    SELECT * FROM usuarios 
                    WHERE nombre LIKE %s 
                    AND id != %s
                ''', (query_string, session['userid']))
                
                resultados = cursor.fetchall()

        cursor.close()
    except Exception as e:
        flash('Error al buscar usuarios.', 'error')
        print(f"Error búsqueda: {e}")
        current_user_data = {'id': session.get('userid'), 'nombre': session.get('username'), 'foto_perfil': None}

    return render_template('buscar.html', resultados=resultados, busqueda=busqueda, user=current_user_data)

@app.route('/chat/<int:receptor_id>', methods=['GET', 'POST'])
def chat(receptor_id):
    if 'login' not in session: return redirect(url_for('login'))
    
    emisor_id = session['userid']
    
    try:
        cursor = get_db_cursor()

        if request.method == 'POST':
            contenido = request.form.get('contenido')
            file = request.files.get('archivo')
            
            filename = None
            tipo_archivo = 'texto'

            if file and allowed_file(file.filename):
                filename = secure_filename(str(datetime.now().timestamp()) + "_" + file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                tipo_archivo = 'imagen' 

            if contenido or filename:
                cursor.execute('''
                    INSERT INTO mensajes (emisor_id, receptor_id, contenido, imagen, tipo_archivo, fecha)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                ''', (emisor_id, receptor_id, contenido, filename, tipo_archivo))
                mysql.connection.commit()
            
            return redirect(url_for('chat', receptor_id=receptor_id))

        cursor.execute('''
            SELECT * FROM mensajes 
            WHERE (emisor_id = %s AND receptor_id = %s) 
               OR (emisor_id = %s AND receptor_id = %s)
            ORDER BY fecha ASC
        ''', (emisor_id, receptor_id, receptor_id, emisor_id))
        mensajes = cursor.fetchall()

        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (receptor_id,))
        receptor = cursor.fetchone()

        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (emisor_id,))
        current_user_data = cursor.fetchone()
        
        cursor.close()
        return render_template('chat.html', receptor=receptor, mensajes=mensajes, user=current_user_data)

    except Exception as e:
        print(f"Error chat: {e}")
        flash('Error al cargar el chat', 'error')
        return redirect(url_for('home'))


@app.route('/perfil/<int:id>')
def perfil(id):
    if 'login' not in session:
        return redirect(url_for('login'))

    try:
        cursor = get_db_cursor()
        # Aseguramos que exista la tabla de seguimientos
        ensure_follows_table(cursor)

        # Datos del usuario del perfil
        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (id,))
        user_data = cursor.fetchone()

        # Contadores de seguidores y seguidos
        cursor.execute('SELECT COUNT(*) AS total FROM follows WHERE followed_id = %s', (id,))
        seguidores = cursor.fetchone()['total']

        cursor.execute('SELECT COUNT(*) AS total FROM follows WHERE follower_id = %s', (id,))
        seguidos = cursor.fetchone()['total']

        # ¿El usuario actual ya sigue a este perfil?
        is_following = False
        if session['userid'] != id:
            cursor.execute(
                'SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s',
                (session['userid'], id)
            )
            is_following = cursor.fetchone() is not None

        # Publicaciones del usuario
        cursor.execute('''
            SELECT posts.*, usuarios.nombre, usuarios.foto_perfil 
            FROM posts 
            JOIN usuarios ON posts.user_id = usuarios.id 
            WHERE posts.user_id = %s 
            ORDER BY posts.fecha DESC
        ''', (id,))
        user_posts = cursor.fetchall()

        # Datos del usuario autenticado (para la barra lateral)
        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (session['userid'],))
        current_user_data = cursor.fetchone()
        cursor.close()

        if user_data:
            return render_template(
                'perfil.html',
                perfil_user=user_data,
                posts=user_posts,
                user=current_user_data,
                seguidores=seguidores,
                seguidos=seguidos,
                is_following=is_following
            )
    except Exception as e:
        print("Error en vista de perfil:", e)

    return redirect(url_for('home'))


@app.route('/actualizar_foto', methods=['POST'])
def actualizar_foto():
    if 'login' not in session: return redirect(url_for('login'))
    
    file = request.files.get('foto_perfil')
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(f"profile_{session['userid']}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            cursor = get_db_cursor() 
            cursor.execute('UPDATE usuarios SET foto_perfil = %s WHERE id = %s', (filename, session['userid']))
            mysql.connection.commit()
            cursor.close()
            flash('Foto actualizada', 'success')
        except Exception as e:
            flash(f'Error al subir foto: {e}', 'error')
        
    return redirect(url_for('perfil', id=session['userid']))

@app.route('/publicar', methods=['POST'])
def publicar():
    if 'login' not in session: return redirect(url_for('login'))

    contenido = request.form.get('contenido')
    file = request.files.get('archivo')
    user_id = session['userid']
    
    filename = None
    tipo_archivo = 'none'

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(str(datetime.now().timestamp()) + "_" + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            tipo_archivo = 'video' if filename.lower().endswith('mp4') else 'imagen'
        except:
            flash('Error al guardar archivo', 'error')
            return redirect(url_for('home'))

    if contenido or filename:
        try:
            cursor = get_db_cursor()
            cursor.execute('INSERT INTO posts (user_id, contenido, imagen, tipo_archivo, fecha) VALUES (%s, %s, %s, %s, NOW())', 
                           (user_id, contenido, filename, tipo_archivo))
            mysql.connection.commit()
            cursor.close()
        except:
            flash('Error de base de datos al publicar', 'error')

    return redirect(url_for('home'))

@app.route('/borrar_post/<string:id>')
def borrar_post(id):
    if 'login' not in session: return redirect(url_for('login'))
    try:
        cursor = get_db_cursor()
        cursor.execute('DELETE FROM posts WHERE id = %s AND user_id = %s', (id, session['userid']))
        mysql.connection.commit()
        cursor.close()
    except: pass
    return redirect(url_for('home'))



@app.route('/seguir/<int:id>', methods=['POST'])
def toggle_follow(id):
    """Permite seguir o dejar de seguir a otro usuario."""
    if 'login' not in session:
        return redirect(url_for('login'))

    follower_id = session['userid']

    # Un usuario no puede seguirse a sí mismo
    if follower_id == id:
        flash('No puedes seguirte a ti mismo.', 'error')
        return redirect(url_for('perfil', id=id))

    try:
        cursor = get_db_cursor()
        ensure_follows_table(cursor)

        # Verificamos si ya lo sigue
        cursor.execute(
            'SELECT 1 FROM follows WHERE follower_id = %s AND followed_id = %s',
            (follower_id, id)
        )
        ya_sigue = cursor.fetchone() is not None

        if ya_sigue:
            cursor.execute(
                'DELETE FROM follows WHERE follower_id = %s AND followed_id = %s',
                (follower_id, id)
            )
            mensaje = 'Has dejado de seguir a este usuario.'
        else:
            cursor.execute(
                'INSERT INTO follows (follower_id, followed_id) VALUES (%s, %s)',
                (follower_id, id)
            )
            mensaje = 'Ahora sigues a este usuario.'

        cursor.connection.commit()
        cursor.close()
        flash(mensaje, 'success')
    except Exception as e:
        print('Error al actualizar seguimiento:', e)
        flash('No se ha podido actualizar el seguimiento.', 'error')

    return redirect(url_for('perfil', id=id))


@app.route('/seguridad', methods=['GET', 'POST'])
def seguridad():
    """Pantalla de cambio de contraseña del usuario."""
    if 'login' not in session:
        return redirect(url_for('login'))

    current_user_data = None

    try:
        cursor = get_db_cursor()
        cursor.execute('SELECT * FROM usuarios WHERE id = %s', (session['userid'],))
        current_user_data = cursor.fetchone()

        if request.method == 'POST':
            actual = request.form.get('password_actual')
            nueva = request.form.get('password_nueva')
            confirmar = request.form.get('password_confirmar')

            if not actual or not nueva or not confirmar:
                flash('Todos los campos son obligatorios.', 'error')
            elif nueva != confirmar:
                flash('La nueva contraseña y su verificación no coinciden.', 'error')
            elif current_user_data is None or current_user_data.get('password') != actual:
                flash('La contraseña actual es incorrecta.', 'error')
            else:
                cursor.execute(
                    'UPDATE usuarios SET password = %s WHERE id = %s',
                    (nueva, session['userid'])
                )
                cursor.connection.commit()
                flash('Contraseña actualizada correctamente.', 'success')

        cursor.close()
    except Exception as e:
        print('Error en la vista de seguridad:', e)
        flash('No se pudo actualizar la contraseña. Inténtalo más tarde.', 'error')

    return render_template('seguridad.html', user=current_user_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['nombre']
        password = request.form['password']
        try:
            cursor = get_db_cursor()
            cursor.execute('SELECT * FROM usuarios WHERE nombre = %s AND password = %s', (username, password,))
            account = cursor.fetchone()
            cursor.close()
            if account:
                session['login'] = True
                session['username'] = account['nombre']
                session['userid'] = account['id']
                return redirect(url_for('home'))
            else:
                flash('Datos incorrectos', 'error')
        except Exception as e:
            flash('Error de conexión. Intenta de nuevo.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        password = request.form.get('password')
        cedula = request.form.get('cedula')
        email = request.form.get('email')
        fecha = request.form.get('fecha_nacimiento')
        genero = request.form.get('genero')
        
        try:
            cursor = get_db_cursor()
            cursor.execute('INSERT INTO usuarios (nombre, password, cedula, email, fecha_nacimiento, genero) VALUES (%s, %s, %s, %s, %s, %s)', 
                        (nombre, password, cedula, email, fecha, genero))
            mysql.connection.commit()
            flash('Registrado correctamente', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error al registrar: {e}', 'error')
            
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
