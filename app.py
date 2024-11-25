from flask import Flask, request, jsonify, url_for
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import secrets
import random
import string



app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas y dominios

# Configuración de claves secretas para Flask y JWT
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)  # Clave para Flask (session)
app.config['JWT_SECRET_KEY'] = secrets.token_urlsafe(32)  # Clave para JWT

# Configuración de Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Cambia esto según tu servidor de correo
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'fianzastt@gmail.com'  # Tu correo electrónico
app.config['MAIL_PASSWORD'] = 'xbak zamo nzri thaj'  # Tu contraseña
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

# Inicializar Mail y JWT
mail = Mail(app)
jwt = JWTManager(app)

# Serializador para la creación de tokens de verificación de email
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def create_connection():
    connection = None
    try:
        connection = mysql.connector.connect(
            host='junction.proxy.rlwy.net',  
            user='root',  
            password='seGINyodjSJtCdGANdxoshXTJKuQNOAV',  
            database='railway',  
            port='46796'
        )
        return connection
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# FUNCION PARA INICIO DE SESION CON VALIDACION DE INGRESOS TAB Y JWT
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    # Verificar si el usuario existe y las credenciales son correctas
    query_user = "SELECT * FROM Usuario WHERE Email = %s AND Contraseña = %s"
    cursor.execute(query_user, (email, password))
    user = cursor.fetchone()
    
    if user:
        # Verificar que el usuario esté activo y haya verificado su correo
        if user['Estado_ID'] != 1:
            connection.close()
            return jsonify({"error": "Tu cuenta no está activa. Contacta al soporte."}), 403
        
        if not user.get('email_verificado', False):
            connection.close()
            return jsonify({"error": "Debes verificar tu correo electrónico para iniciar sesión."}), 403

        # Obtener el ID del usuario
        user_id = user['ID_Usuario']
        print(f"ID del usuario: {user_id}")
        
        # Crear token de acceso JWT
        access_token = create_access_token(identity=user_id)

        # Verificar si el usuario pertenece a algún grupo o es administrador de uno
        pertenece_a_grupo = False
        es_admin_grupo = False
        grupos_administrados = []
        grupos_pertenecientes = []

        # Verificar si es administrador de algún grupo
        cursor.execute("SELECT ID_Grupo, Nombre_Grupo FROM Grupo WHERE ID_Admin = %s", (user_id,))
        grupos_admin = cursor.fetchall()
        if grupos_admin:
            es_admin_grupo = True
            grupos_administrados = grupos_admin

        # Verificar si es miembro de algún grupo
        cursor.execute("""
            SELECT g.ID_Grupo, g.Nombre_Grupo 
            FROM Grupo g
            JOIN Miembro_Grupo mg ON g.ID_Grupo = mg.ID_Grupo
            WHERE mg.ID_Usuario = %s OR mg.Email = %s
        """, (user_id, email))
        grupos_miembro = cursor.fetchall()
        if grupos_miembro:
            pertenece_a_grupo = True
            grupos_pertenecientes = grupos_miembro

        # Verificar si el usuario tiene ingresos registrados
        query_income = """
        SELECT ID_Ingreso, Descripcion, Monto, Fecha, Periodicidad, EsFijo 
        FROM Ingreso 
        WHERE ID_Usuario = %s
        """
        cursor.execute(query_income, (user_id,))
        incomes = cursor.fetchall()

        hasIncome = bool(incomes)
        mostrar_tab_periodo = False
        descripcion = None
        fecha_ultimo_ingreso = None

        if hasIncome:
            print(f"El usuario tiene {len(incomes)} ingresos registrados.")
            # Agrupar ingresos no fijos por descripción y seleccionar el más reciente
            ingresos_no_fijos = {income['Descripcion']: income for income in incomes if income['EsFijo'] == 0}

            # Verificar si hay ingresos no fijos registrados
            if ingresos_no_fijos:
                for descripcion, income in ingresos_no_fijos.items():
                    fecha_ultimo_ingreso = income['Fecha']
                    periodicidad = income['Periodicidad']
                    
                    # Calcular la fecha de comparación según la periodicidad
                    if periodicidad == 'Diario':
                        fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(days=1)
                    elif periodicidad == 'Semanal':
                        fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=1)
                    elif periodicidad == 'Quincenal':
                        fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=2)
                    elif periodicidad == 'Mensual':
                        fecha_siguiente_ingreso = fecha_ultimo_ingreso + relativedelta(months=1)

                    if datetime.now().date() >= fecha_siguiente_ingreso:
                        mostrar_tab_periodo = True
                        break

        connection.close()

        # Generar la respuesta final sin almacenar en localStorage
        response_data = {
            "message": "Login exitoso",
            "token": access_token,
            "user": user,
            "hasIncome": hasIncome,
            "showFloatingTabIncome": mostrar_tab_periodo,
            "descripcionIngreso": descripcion,
            "fechaUltimoIngreso": fecha_ultimo_ingreso.strftime('%d/%m/%Y') if fecha_ultimo_ingreso else None,
            "showFloatingTab": not hasIncome and not incomes,
            "pertenece_a_grupo": pertenece_a_grupo,
            "es_admin_grupo": es_admin_grupo,
            "grupos_administrados": grupos_administrados,
            "grupos_pertenecientes": grupos_pertenecientes
        }

        return jsonify(response_data), 200
    else:
        connection.close()
        return jsonify({"error": "Correo o contraseña incorrectos"}), 401





# FUNCION DE REGISTRO DE USUARIOS (No protegida)
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    print(f"Datos recibidos para registro: {data}")

    email = data.get('email')
    password = data.get('password')
    nombre = data.get('nombre')
    apellido_p = data.get('apellido_p')
    apellido_m = data.get('apellido_m')
    fecha_cumple = data.get('fecha_cumple')
    contacto = data.get('contacto', None)

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor()

    try:
        # Verificar si el usuario ya existe
        query_check = "SELECT * FROM Usuario WHERE Email = %s"
        cursor.execute(query_check, (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            return jsonify({"error": "El usuario ya existe"}), 409

        # Insertar nuevo usuario con Estado_ID = 1
        query = """
        INSERT INTO Usuario (Nombre, Apellido_P, Apellido_M, Email, Contraseña, Estado_ID, Fecha_Cumple, Contacto)
        VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
        """
        cursor.execute(query, (nombre, apellido_p, apellido_m, email, password, fecha_cumple, contacto))
        connection.commit()

        # Enviar correo de verificación
        token = s.dumps(email, salt='email-confirm')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        
        # Configurar el cuerpo del mensaje en HTML
        html_body = f"""
        <p>Por favor, haz clic <a href="{confirm_url}">AQUI</a> para verificar tu correo electrónico.</p>
        """
        
        msg = Message('Confirma tu correo electrónico', sender='your_email@gmail.com', recipients=[email])
        msg.html = html_body  # Usar el cuerpo en HTML
        mail.send(msg)

        return jsonify({"message": "Usuario registrado exitosamente"}), 201

    except mysql.connector.errors.IntegrityError as e:
        return jsonify({"error": "El usuario ya existe"}), 409

    finally:
        connection.close()



@app.route('/confirm_email/<token>', methods=['GET'])
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)
    except SignatureExpired:
        return jsonify({"error": "El enlace de verificación ha expirado."}), 400
    
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor()

    # Actualizar el campo email_verificado a True
    query = "UPDATE Usuario SET email_verificado = TRUE WHERE Email = %s"
    cursor.execute(query, (email,))
    connection.commit()

    connection.close()

    # Enviar una respuesta HTML para ser manejada por React
    return '''
    <html>
        <body>
            <script>
                window.location.href = "http://localhost:3000/email-verified";
            </script>
        </body>
    </html>
    ''', 200

@app.route('/api/ingreso', methods=['POST'])
@jwt_required()
def agregar_ingreso():
    data = request.json
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT
    monto = data.get('monto')
    descripcion = data.get('descripcion', None)
    tipo = data.get('tipo', None)
    periodicidad = data.get('periodicidad', None)
    es_fijo = data.get('esFijo', None)
    es_periodico = data.get('es_periodico', True)  # Por defecto, es periódico si no se especifica lo contrario
    
    # Verificar si se envió una fecha en el payload; si no, usar la fecha actual
    fecha = data.get('fecha', None)
    if fecha:
        try:
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()  # Convertir la fecha de string a objeto datetime
        except ValueError:
            return jsonify({"error": "Formato de fecha incorrecto. Use YYYY-MM-DD."}), 400
    else:
        fecha = datetime.now().date()  # Usar la fecha actual si no se envió una en el payload

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Si el frontend solo envía el monto, buscamos un ingreso existente con la misma descripción
    if descripcion is None or tipo is None:
        # Si solo se recibe el monto, estamos actualizando el ingreso periódico sin cambiar la descripción ni otros datos
        print("Actualización de ingreso con solo monto y fecha actual")

        query_find_ingreso = """
        SELECT ID_Ingreso, Descripcion, Tipo, Periodicidad, EsFijo, EsPeriodico
        FROM Ingreso
        WHERE ID_Usuario = %s AND Descripcion = %s
        ORDER BY Fecha DESC
        LIMIT 1
        """
        cursor.execute(query_find_ingreso, (id_usuario, data.get('descripcion')))
        ingreso_existente = cursor.fetchone()

        if ingreso_existente:
            # Si encontramos un ingreso anterior, usamos los mismos datos excepto monto y fecha
            descripcion = ingreso_existente[1]
            tipo = ingreso_existente[2]
            periodicidad = ingreso_existente[3]
            es_fijo = ingreso_existente[4]
            es_periodico = ingreso_existente[5]

            # Insertamos un nuevo ingreso con el monto y la fecha actualizada
            query_insert = """
            INSERT INTO Ingreso (Descripcion, Monto, Fecha, Tipo, ID_Usuario, Periodicidad, EsFijo, EsPeriodico)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (descripcion, monto, fecha, tipo, id_usuario, periodicidad, es_fijo, es_periodico))
            connection.commit()

            print(f"Ingreso con solo monto y fecha actual procesado correctamente para {descripcion}")
            connection.close()
            return jsonify({"message": "Ingreso actualizado con éxito"}), 201
        else:
            connection.close()
            return jsonify({"error": "No se encontró un ingreso previo para actualizar"}), 404

    # Si se proporcionan todos los datos, estamos insertando un nuevo ingreso o actualizando uno existente
    else:
        print(f"Datos recibidos para agregar o actualizar ingreso: {data}")
        
        # Verificar si ya existe un ingreso con la misma descripción
        query_check = """
        SELECT ID_Ingreso, Fecha
        FROM Ingreso
        WHERE Descripcion = %s AND ID_Usuario = %s
        ORDER BY Fecha DESC
        LIMIT 1
        """
        cursor.execute(query_check, (descripcion, id_usuario))
        ingreso_existente = cursor.fetchone()

        if ingreso_existente:
            # Comprobar si el periodo ha pasado basándose en la periodicidad
            fecha_ultimo_ingreso = ingreso_existente[1]
            fecha_siguiente_ingreso = None

            # Determinar la fecha de comparación en base a la periodicidad
            if periodicidad == 'Diario':
                fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(days=1)
            elif periodicidad == 'Semanal':
                fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=1)
            elif periodicidad == 'Quincenal':
                fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=2)
            elif periodicidad == 'Mensual':
                fecha_siguiente_ingreso = fecha_ultimo_ingreso + relativedelta(months=1)

            # Si el periodo ha pasado, insertamos un nuevo ingreso
            if fecha >= fecha_siguiente_ingreso:
                query_insert = """
                INSERT INTO Ingreso (Descripcion, Monto, Fecha, Tipo, ID_Usuario, Periodicidad, EsFijo, EsPeriodico)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query_insert, (descripcion, monto, fecha, tipo, id_usuario, periodicidad, es_fijo, es_periodico))
                print(f"Ingreso periódico insertado correctamente para {descripcion}")
            else:
                print("El periodo aún no ha pasado, no se actualiza")
                return jsonify({"message": "El periodo aún no ha pasado, no es necesario actualizar el ingreso"}), 200
        else:
            # Insertar un nuevo ingreso
            print(f"Insertando nuevo ingreso para {descripcion}")
            query_insert = """
            INSERT INTO Ingreso (Descripcion, Monto, Fecha, Tipo, ID_Usuario, Periodicidad, EsFijo, EsPeriodico)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (descripcion, monto, fecha, tipo, id_usuario, periodicidad, es_fijo, es_periodico))

        connection.commit()
        print(f"Ingreso procesado correctamente para {descripcion}")
        connection.close()

        return jsonify({"message": "Ingreso procesado exitosamente"}), 201



# RUTA PARA OBTENER INGRESOS FILTRADOS
@app.route('/api/income/filtered', methods=['POST'])
@jwt_required()
def obtener_ingresos_filtrados():
    user_id = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT
    data = request.json
    tipo = data.get('tipo')
    es_fijo = data.get('esFijo')  # Recibir el filtro de fijo/no fijo
    periodicidad = data.get('periodicidad')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Construir la consulta SQL
    query = """
    SELECT Descripcion, SUM(Monto) as Monto
    FROM Ingreso
    WHERE ID_Usuario = %s
    """
    params = [user_id]

    if tipo:
        query += " AND Tipo = %s"
        params.append(tipo)
    
    if es_fijo is not None:  # Manejar el filtro de fijo/no fijo
        query += " AND EsFijo = %s"
        params.append(1 if es_fijo == 'fijo' else 0)

    if periodicidad:
        query += " AND Periodicidad = %s"
        params.append(periodicidad)

    if fecha_inicio and fecha_fin:
        query += " AND Fecha BETWEEN %s AND %s"
        params.append(fecha_inicio)
        params.append(fecha_fin)

    query += " GROUP BY Descripcion"

    cursor.execute(query, params)
    ingresos = cursor.fetchall()

    connection.close()

    return jsonify(ingresos), 200

# RUTA PARA OBTENER INGRESOS PARA TABLA
@app.route('/api/user/incomes', methods=['GET'])
@jwt_required()
def get_user_incomes():
    user_id = get_jwt_identity()

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT ID_Ingreso, Descripcion, Monto, Periodicidad, EsFijo, Tipo, Fecha, EsPeriodico
    FROM Ingreso
    WHERE ID_Usuario = %s
    ORDER BY Fecha DESC
    """
    cursor.execute(query, (user_id,))
    incomes = cursor.fetchall()

    # Mapear el valor de EsPeriodico a "Periódico" o "Único"
    for income in incomes:
        income['TipoPeriodico'] = 'Periódico' if income['EsPeriodico'] else 'Único'

    connection.close()

    return jsonify(incomes), 200


# RUTA PARA ELIMINAR INGRESOS 
@app.route('/api/user/incomes/<int:income_id>', methods=['DELETE'])
@jwt_required()
def delete_income(income_id):
    user_id = get_jwt_identity()

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Obtener la información del ingreso antes de eliminarlo
    query_select = "SELECT * FROM Ingreso WHERE ID_Ingreso = %s AND ID_Usuario = %s"
    cursor.execute(query_select, (income_id, user_id))
    income = cursor.fetchone()

    if not income:
        connection.close()
        return jsonify({"error": "Ingreso no encontrado"}), 404

    # Loguear la información del ingreso a eliminar
    print(f"Ingreso a eliminar: {income}")

    # Proceder a eliminar el ingreso
    query_delete = "DELETE FROM Ingreso WHERE ID_Ingreso = %s AND ID_Usuario = %s"
    cursor.execute(query_delete, (income_id, user_id))
    connection.commit()

    connection.close()

    return jsonify({"message": "Ingreso eliminado exitosamente."}), 200


@app.route('/api/user/update_income/<int:id_ingreso>', methods=['PUT'])
@jwt_required()
def update_income(id_ingreso):
    user_id = get_jwt_identity()
    data = request.json

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Actualizar el ingreso con los nuevos datos, incluyendo la fecha
    query = """
    UPDATE Ingreso
    SET Descripcion = %s, Monto = %s, Periodicidad = %s, EsFijo = %s, Tipo = %s, Fecha = %s
    WHERE ID_Ingreso = %s AND ID_Usuario = %s
    """
    cursor.execute(query, (
        data.get('Descripcion'),
        data.get('Monto'),
        data.get('Periodicidad'),
        data.get('EsFijo'),
        data.get('Tipo'),
        data.get('Fecha'),  # Asegúrate de que la fecha se esté enviando en el formato correcto (YYYY-MM-DD)
        id_ingreso,
        user_id
    ))
    
    connection.commit()
    connection.close()

    return jsonify({"message": "Ingreso actualizado exitosamente."}), 200




@app.route('/api/user/income/<int:id_ingreso>', methods=['GET'])
@jwt_required()
def get_income_by_id(id_ingreso):
    user_id = get_jwt_identity()

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT ID_Ingreso, Descripcion, Monto, Periodicidad, EsFijo, Tipo, Fecha, EsPeriodico
    FROM Ingreso
    WHERE ID_Ingreso = %s AND ID_Usuario = %s
    """
    cursor.execute(query, (id_ingreso, user_id))
    income = cursor.fetchone()

    connection.close()

    if income:
        return jsonify(income), 200
    else:
        return jsonify({"error": "Ingreso no encontrado"}), 404
    

@app.route('/api/gasto', methods=['POST'])
@jwt_required()
def agregar_gasto():
    data = request.json
    print("Datos recibidos en el backend para gasto:", data)  # Para verificar el payload en consola

    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT
    descripcion = data.get('descripcion')
    monto = data.get('monto')
    fecha = data.get('fecha', None)
    categoria = data.get('categoria')
    id_subcategoria = data.get('id_subcategoria')  # Asegurarse de que sea un ID
    periodicidad = data.get('periodicidad', None)  # Se espera como None si es único
    periodico = data.get('periodico', 1)  # Por defecto, asumir que es periódico

    # Validación de la fecha, si no está en el payload, se usa la fecha actual
    if fecha:
        try:
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Formato de fecha incorrecto. Use YYYY-MM-DD."}), 400
    else:
        fecha = datetime.now().date()

    # Validación de campos obligatorios
    if not descripcion or not monto or not categoria:
        return jsonify({"error": "Datos incompletos"}), 400

    # Configuración de la conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Si es único, periodicidad será NULL
    query = """
    INSERT INTO Gasto (Descripcion, Monto, Fecha, Categoria, ID_Subcategoria, Periodico, ID_Usuario, Periodicidad)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        descripcion,
        monto,
        fecha,
        categoria,
        id_subcategoria,
        periodico,
        id_usuario,
        periodicidad if periodico == 1 else None  # Almacena periodicidad solo si es periódico
    ))

    connection.commit()
    connection.close()

    return jsonify({"message": "Gasto registrado con éxito"}), 201






@app.route('/api/user/gastos', methods=['GET'])
@jwt_required()
def obtener_gastos_usuario():
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Actualizar la consulta eliminando `G.ID_Grupo`
    query = """
    SELECT G.ID_Gasto, G.Descripcion, G.Monto, G.Fecha, G.Categoria, G.Periodicidad, 
           G.Periodico, S.Nombre AS Subcategoria
    FROM Gasto G
    LEFT JOIN Subcategoria S ON G.ID_Subcategoria = S.ID_Subcategoria
    WHERE G.ID_Usuario = %s
    ORDER BY G.Fecha DESC
    """
    cursor.execute(query, (id_usuario,))
    gastos = cursor.fetchall()

    connection.close()

    # Convertir el resultado en formato JSON
    gastos_json = [
        {
            "ID_Gasto": gasto["ID_Gasto"],
            "Descripcion": gasto["Descripcion"],
            "Monto": gasto["Monto"],
            "Fecha": gasto["Fecha"].strftime('%Y-%m-%d'),  # Formato de fecha para JSON
            "Categoria": gasto["Categoria"],
            "Periodicidad": gasto["Periodicidad"],
            "Periodico": gasto["Periodico"],
            "Subcategoria": gasto["Subcategoria"]  # Añadir el nombre de la subcategoría
        }
        for gasto in gastos
    ]

    return jsonify(gastos_json), 200





@app.route('/api/gasto/<int:id_gasto>', methods=['PUT'])
@jwt_required()
def actualizar_gasto(id_gasto):
    data = request.json
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT

    descripcion = data.get('descripcion')
    monto = data.get('monto')
    fecha = data.get('fecha')
    categoria = data.get('categoria')
    periodico = data.get('periodico')
    id_grupo = data.get('id_grupo')

    if not descripcion or not monto or not fecha or not categoria:
        return jsonify({"error": "Datos incompletos"}), 400

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Actualizar el gasto existente
    query = """
    UPDATE Gasto
    SET Descripcion = %s, Monto = %s, Fecha = %s, Categoria = %s, Periodico = %s, ID_Grupo = %s
    WHERE ID_Gasto = %s AND ID_Usuario = %s
    """
    cursor.execute(query, (descripcion, monto, fecha, categoria, periodico, id_grupo, id_gasto, id_usuario))

    connection.commit()
    connection.close()

    return jsonify({"message": "Gasto actualizado con éxito"}), 200



@app.route('/api/gasto/<int:id_gasto>', methods=['DELETE'])
@jwt_required()
def eliminar_gasto(id_gasto):
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Eliminar el gasto
    query = """
    DELETE FROM Gasto WHERE ID_Gasto = %s AND ID_Usuario = %s
    """
    cursor.execute(query, (id_gasto, id_usuario))

    connection.commit()
    connection.close()

    return jsonify({"message": "Gasto eliminado con éxito"}), 200



@app.route('/api/gasto/filtered', methods=['POST'])
@jwt_required()
def filtrar_gastos_usuario():
    data = request.json
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT
    categoria = data.get('categoria', None)
    periodico = data.get('periodico', None)
    fecha_inicio = data.get('fecha_inicio', None)
    fecha_fin = data.get('fecha_fin', None)

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Construir la consulta de filtrado dinámico
    query = """
    SELECT ID_Gasto, Descripcion, Monto, Fecha, Categoria, Periodico
    FROM Gasto
    WHERE ID_Usuario = %s
    """
    query_params = [id_usuario]

    if categoria:
        query += " AND Categoria = %s"
        query_params.append(categoria)
    
    if periodico is not None:
        query += " AND Periodico = %s"
        query_params.append(periodico)
    
    if fecha_inicio and fecha_fin:
        query += " AND Fecha BETWEEN %s AND %s"
        query_params.append(fecha_inicio)
        query_params.append(fecha_fin)

    query += " ORDER BY Fecha DESC"

    cursor.execute(query, tuple(query_params))
    gastos = cursor.fetchall()

    connection.close()

    # Transformar los resultados en un formato JSON
    gastos_json = [
        {
            "ID_Gasto": gasto[0],
            "Descripcion": gasto[1],
            "Monto": gasto[2],
            "Fecha": gasto[3].strftime('%Y-%m-%d'),
            "Categoria": gasto[4],
            "Periodico": gasto[5]
        }
        for gasto in gastos
    ]

    return jsonify(gastos_json), 200



@app.route('/api/subcategorias/<string:categoria>', methods=['GET'])
@jwt_required()
def obtener_subcategorias(categoria):
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Buscar subcategorías según la categoría
    query = "SELECT ID_Subcategoria, Nombre FROM Subcategoria WHERE Categoria = %s"
    cursor.execute(query, (categoria,))
    subcategorias = cursor.fetchall()

    connection.close()

    # Retornar el ID y el Nombre de cada subcategoría
    return jsonify(subcategorias), 200

    # Obtener metas financieras
@app.route('/api/metas', methods=['GET'])
@jwt_required()
def obtener_metas():
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    query_metas = """
        SELECT ID_Meta, Nombre, MontoObjetivo, FechaInicio, FechaTermino, MesesParaMeta, AhorroMensual 
        FROM Metas 
        WHERE ID_Usuario = %s
    """
    cursor.execute(query_metas, (user_id,))
    metas = cursor.fetchall()

    for meta in metas:
        query_ahorrado = """
            SELECT SUM(MontoAhorrado) as MontoAhorrado 
            FROM TransaccionesMeta 
            WHERE ID_Meta = %s
        """
        cursor.execute(query_ahorrado, (meta['ID_Meta'],))
        resultado_ahorrado = cursor.fetchone()
        meta['MontoAhorrado'] = resultado_ahorrado['MontoAhorrado'] if resultado_ahorrado['MontoAhorrado'] is not None else 0

    connection.close()
    return jsonify(metas), 200



#Crear metas
@app.route('/api/metas', methods=['POST'])
@jwt_required()
def crear_meta():
    user_id = get_jwt_identity()
    data = request.json
    nombre = data.get('nombre')
    monto_objetivo = data.get('montoObjetivo')
    fecha_inicio = data.get('fechaInicio')
    fecha_termino = data.get('fechaTermino')
    meses_para_meta = data.get('mesesParaMeta')
    ahorro_mensual = data.get('ahorroMensual')
    
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor()
    query = """
        INSERT INTO Metas (ID_Usuario, Nombre, MontoObjetivo, FechaInicio, FechaTermino, MesesParaMeta, AhorroMensual)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (user_id, nombre, monto_objetivo, fecha_inicio, fecha_termino, meses_para_meta, ahorro_mensual))
    connection.commit()
    
    connection.close()
    return jsonify({"message": "Meta creada exitosamente"}), 201



@app.route('/api/validar-ingresos-gastos', methods=['GET'])
@jwt_required()
def validar_ingresos_gastos():
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    # Contar ingresos del usuario
    query_ingresos = "SELECT COUNT(*) as total FROM Ingreso WHERE ID_Usuario = %s"
    cursor.execute(query_ingresos, (user_id,))
    total_ingresos = cursor.fetchone()['total']
    
    # Contar gastos del usuario
    query_gastos = "SELECT COUNT(*) as total FROM Gasto WHERE ID_Usuario = %s"
    cursor.execute(query_gastos, (user_id,))
    total_gastos = cursor.fetchone()['total']
    
    connection.close()
    
    if total_ingresos >= 3 and total_gastos >= 3:
        return jsonify({"valido": True}), 200
    else:
        return jsonify({"valido": False}), 200

@app.route('/api/promedios', methods=['GET'])
@jwt_required()
def obtener_promedios():
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    # Calcular promedio de ingresos del usuario
    query_promedio_ingresos = "SELECT AVG(Monto) as promedio_ingresos FROM Ingreso WHERE ID_Usuario = %s"
    cursor.execute(query_promedio_ingresos, (user_id,))
    promedio_ingresos = cursor.fetchone()['promedio_ingresos']
    
    # Calcular promedio de gastos del usuario
    query_promedio_gastos = "SELECT AVG(Monto) as promedio_gastos FROM Gasto WHERE ID_Usuario = %s"
    cursor.execute(query_promedio_gastos, (user_id,))
    promedio_gastos = cursor.fetchone()['promedio_gastos']
    
    connection.close()
    
    # Calcular el valor disponible para metas
    disponible_para_metas = promedio_ingresos - promedio_gastos
    
    return jsonify({
        "promedio_ingresos": promedio_ingresos,
        "promedio_gastos": promedio_gastos,
        "disponible_para_metas": disponible_para_metas
    }), 200

# Eliminar meta financiera
@app.route('/api/metas/<int:id_meta>', methods=['DELETE'])
@jwt_required()
def eliminar_meta(id_meta):
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    try:
        cursor = connection.cursor()
        
        # Primero eliminar transacciones asociadas
        query_transacciones = "DELETE FROM TransaccionesMeta WHERE ID_Meta = %s"
        cursor.execute(query_transacciones, (id_meta,))
        
        # Luego eliminar la meta
        query_meta = "DELETE FROM Metas WHERE ID_Meta = %s AND ID_Usuario = %s"
        cursor.execute(query_meta, (id_meta, user_id))
        
        connection.commit()
    except mysql.connector.Error as err:
        connection.rollback()
        return jsonify({"error": str(err)}), 500
    finally:
        connection.close()

    return '', 204




@app.route('/api/ingresos/mensuales', methods=['GET'])
@jwt_required()
def obtener_ingresos_mensuales():
    user_id = get_jwt_identity()
    mes = request.args.get('mes')
    año = request.args.get('año')

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT ID_Ingreso as ID, Descripcion, Monto, Fecha
    FROM Ingreso
    WHERE ID_Usuario = %s AND MONTH(Fecha) = %s AND YEAR(Fecha) = %s
    """
    cursor.execute(query, (user_id, mes, año))
    ingresos = cursor.fetchall()

    connection.close()
    return jsonify(ingresos), 200


@app.route('/api/gastos/mensuales', methods=['GET'])
@jwt_required()
def obtener_gastos_mensuales():
    user_id = get_jwt_identity()
    mes = request.args.get('mes')
    año = request.args.get('año')

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT ID_Gasto as ID, Descripcion, Monto, Fecha
    FROM Gasto
    WHERE ID_Usuario = %s AND MONTH(Fecha) = %s AND YEAR(Fecha) = %s
    """
    cursor.execute(query, (user_id, mes, año))
    gastos = cursor.fetchall()

    connection.close()
    return jsonify(gastos), 200

@app.route('/api/totales_financieros', methods=['GET'])
@jwt_required()
def obtener_totales_financieros():
    user_id = get_jwt_identity()
    filters = request.args
    mes = filters.get('mes')
    año = filters.get('año')

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Consulta para obtener los totales de ingresos y gastos por mes
    query_ingresos = """
    SELECT 
        MONTH(Fecha) as mes, 
        YEAR(Fecha) as año, 
        SUM(Monto) as total_ingresos
    FROM Ingreso
    WHERE ID_Usuario = %s
    GROUP BY YEAR(Fecha), MONTH(Fecha)
    ORDER BY YEAR(Fecha), MONTH(Fecha)
    """

    query_gastos = """
    SELECT 
        MONTH(Fecha) as mes, 
        YEAR(Fecha) as año, 
        SUM(Monto) as total_gastos
    FROM Gasto
    WHERE ID_Usuario = %s
    GROUP BY YEAR(Fecha), MONTH(Fecha)
    ORDER BY YEAR(Fecha), MONTH(Fecha)
    """

    # Ejecutar las consultas y obtener los resultados
    cursor.execute(query_ingresos, (user_id,))
    ingresos_por_mes = cursor.fetchall()

    cursor.execute(query_gastos, (user_id,))
    gastos_por_mes = cursor.fetchall()

    # Combinar los datos de ingresos y gastos en una sola lista
    monthly_totals = []
    ingresos_dict = {(ingreso['año'], ingreso['mes']): ingreso['total_ingresos'] for ingreso in ingresos_por_mes}
    gastos_dict = {(gasto['año'], gasto['mes']): gasto['total_gastos'] for gasto in gastos_por_mes}

    for (año, mes) in set(ingresos_dict.keys()).union(gastos_dict.keys()):
        monthly_totals.append({
            'año': año,
            'mes': mes,
            'total_ingresos': ingresos_dict.get((año, mes), 0),
            'total_gastos': gastos_dict.get((año, mes), 0)
        })

    # Ordenar los resultados por año y mes
    monthly_totals = sorted(monthly_totals, key=lambda x: (x['año'], x['mes']))

    connection.close()
    return jsonify(monthly_totals), 200



@app.route('/api/totales_financieros_mes', methods=['GET'])
@jwt_required()
def obtener_totales_financieros_mes():
    user_id = get_jwt_identity()
    mes = request.args.get('mes')
    año = request.args.get('año')

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    # Consulta para obtener el total de ingresos para el mes y año seleccionados
    query_ingresos = """
    SELECT SUM(Monto) as total_ingresos
    FROM Ingreso
    WHERE ID_Usuario = %s AND MONTH(Fecha) = %s AND YEAR(Fecha) = %s
    """
    cursor.execute(query_ingresos, (user_id, mes, año))
    total_ingresos = cursor.fetchone()['total_ingresos'] or 0

    # Consulta para obtener el total de gastos para el mes y año seleccionados
    query_gastos = """
    SELECT SUM(Monto) as total_gastos
    FROM Gasto
    WHERE ID_Usuario = %s AND MONTH(Fecha) = %s AND YEAR(Fecha) = %s
    """
    cursor.execute(query_gastos, (user_id, mes, año))
    total_gastos = cursor.fetchone()['total_gastos'] or 0

    connection.close()

    return jsonify({"total_ingresos": total_ingresos, "total_gastos": total_gastos}), 200


def generate_unique_code(cursor):
    while True:
        # Generar un código alfanumérico de 8 caracteres en mayúsculas
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # Verificar si el código ya existe en la tabla 'Grupo'
        cursor.execute("SELECT COUNT(*) as count FROM Grupo WHERE Codigo_Invitacion = %s", (code,))
        result = cursor.fetchone()
        if result["count"] == 0:  # Verificamos el conteo usando la clave del diccionario
            return code


@app.route('/api/crear_grupo', methods=['POST'])
@jwt_required()
def crear_grupo():
    data = request.json
    nombre_grupo = data.get('nombre_grupo')
    descripcion = data.get('descripcion')
    miembros = data.get('miembros', [])
    user_id = get_jwt_identity()  # Obtener el ID del usuario que está creando el grupo

    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Obtener el correo del usuario que está creando el grupo
        cursor.execute("SELECT Email FROM Usuario WHERE ID_Usuario = %s", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            return jsonify({"error": "Usuario no encontrado"}), 404
        user_email = user_data["Email"]

        # Generar un código de invitación único
        codigo_invitacion = generate_unique_code(cursor)

        # Insertar el grupo en la tabla `Grupo`
        cursor.execute("""
            INSERT INTO Grupo (Nombre_Grupo, Descripcion, ID_Admin, Codigo_Invitacion)
            VALUES (%s, %s, %s, %s)
        """, (nombre_grupo, descripcion, user_id, codigo_invitacion))
        connection.commit()

        # Obtener el ID del grupo recién creado
        grupo_id = cursor.lastrowid

        # Insertar al usuario creador como miembro del grupo con su correo
        cursor.execute("""
            INSERT INTO Miembro_Grupo (ID_Usuario, ID_Grupo, Email, Confirmado)
            VALUES (%s, %s, %s, %s)
        """, (user_id, grupo_id, user_email, 1))  # Confirmado = 1 para el creador del grupo
        
        # Procesar los miembros adicionales y enviarles una invitación por correo
        for email in miembros:
            cursor.execute("SELECT ID_Usuario FROM Usuario WHERE Email = %s", (email,))
            usuario = cursor.fetchone()
            id_usuario = usuario['ID_Usuario'] if usuario else None

            # Insertar el miembro en la tabla Miembro_Grupo con Confirmado = 0
            cursor.execute("""
                INSERT INTO Miembro_Grupo (ID_Usuario, ID_Grupo, Email, Confirmado)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, grupo_id, email, 0))

            # Enviar correo de invitación
            send_invitation_email(email, grupo_id, nombre_grupo)

        connection.commit()

        # Devolver el enlace de invitación
        invitation_link = f"https://tuapp.com/invite/{codigo_invitacion}"
        return jsonify({"message": "Grupo creado exitosamente", "invitationLink": invitation_link}), 201
    
    except mysql.connector.Error as e:
        connection.rollback()
        return jsonify({"error": f"Error al crear el grupo: {str(e)}"}), 500
    
    finally:
        cursor.close()
        connection.close()

# Registrar una nueva transacción para una meta
@app.route('/api/metas/<int:id_meta>/transacciones', methods=['POST'])
@jwt_required()
def registrar_transaccion(id_meta):
    user_id = get_jwt_identity()
    data = request.json
    monto_ahorrado = data.get('montoAhorrado')
    fecha_transaccion = data.get('fechaTransaccion')
    
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor()
    query = """
        INSERT INTO TransaccionesMeta (ID_Meta, MontoAhorrado, FechaTransaccion)
        VALUES (%s, %s, %s)
    """
    cursor.execute(query, (id_meta, monto_ahorrado, fecha_transaccion))
    connection.commit()
    
    connection.close()
    return jsonify({"message": "Transacción registrada exitosamente"}), 201



@app.route('/api/metas/<int:id_meta>', methods=['GET'])
@jwt_required()
def obtener_meta(id_meta):
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    query_meta = """
        SELECT ID_Meta, Nombre, MontoObjetivo, FechaInicio, FechaTermino, MesesParaMeta, AhorroMensual
        FROM Metas
        WHERE ID_Meta = %s AND ID_Usuario = %s
    """
    cursor.execute(query_meta, (id_meta, user_id))
    meta = cursor.fetchone()

    if meta:
        query_ahorrado = """
            SELECT COALESCE(SUM(MontoAhorrado), 0) as MontoAhorrado
            FROM TransaccionesMeta
            WHERE ID_Meta = %s
        """
        cursor.execute(query_ahorrado, (id_meta,))
        resultado_ahorrado = cursor.fetchone()
        meta['MontoAhorrado'] = resultado_ahorrado['MontoAhorrado'] if resultado_ahorrado['MontoAhorrado'] is not None else 0

        query_transacciones = """
            SELECT ID_Transaccion, MontoAhorrado, FechaTransaccion
            FROM TransaccionesMeta
            WHERE ID_Meta = %s
        """
        cursor.execute(query_transacciones, (id_meta,))
        meta['transacciones'] = cursor.fetchall()

    connection.close()
    return jsonify(meta), 200


@app.route('/api/metas/<int:id_meta>/transacciones', methods=['GET'])
@jwt_required()
def obtener_transacciones(id_meta):
    user_id = get_jwt_identity()
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500
    
    cursor = connection.cursor(dictionary=True)
    query = """
        SELECT ID_Transaccion, MontoAhorrado, FechaTransaccion
        FROM TransaccionesMeta
        WHERE ID_Meta = %s
    """
    cursor.execute(query, (id_meta,))
    transacciones = cursor.fetchall()

    connection.close()
    return jsonify(transacciones), 200





def send_invitation_email(email, grupo_id, nombre_grupo):
    # URL para que el usuario acepte la invitación
    accept_url = f"http://localhost:5000/api/accept_invitation?grupo_id={grupo_id}&email={email}"
    msg = Message(
        subject="Invitación a unirse al grupo financiero",
        sender="tu_correo@example.com",
        recipients=[email],
        body=f"Has sido invitado a unirte al grupo '{nombre_grupo}'. Haz clic en el siguiente enlace para aceptar la invitación:\n{accept_url}"
    )
    mail.send(msg)       
        
    
@app.route('/api/accept_invitation', methods=['GET'])
def accept_invitation():
    grupo_id = request.args.get('grupo_id')
    email = request.args.get('email')

    connection = create_connection()
    cursor = connection.cursor()

    try:
        # Actualizar el campo Confirmado a 1 para el miembro
        cursor.execute("""
            UPDATE Miembro_Grupo
            SET Confirmado = 1
            WHERE ID_Grupo = %s AND Email = %s
        """, (grupo_id, email))
        connection.commit()

        return jsonify({"message": "Invitación aceptada exitosamente"}), 200
    
    except mysql.connector.Error as e:
        connection.rollback()
        return jsonify({"error": f"Error al aceptar la invitación: {str(e)}"}), 500
    
    finally:
        cursor.close()
        connection.close()




@app.route('/api/grupos', methods=['GET'])
@jwt_required()
def obtener_grupos_usuario():
    user_id = get_jwt_identity()

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)
    try:
        # Obtener los grupos en los que el usuario pertenece y está confirmado
        query_grupos = """
        SELECT g.ID_Grupo, g.Nombre_Grupo, g.Descripcion, 
               CONCAT(u.Nombre, ' ', u.Apellido_P, ' ', u.Apellido_M) AS Nombre_Admin,
               CASE WHEN g.ID_Admin = %s THEN 1 ELSE 0 END AS es_admin
        FROM Grupo g
        JOIN Usuario u ON g.ID_Admin = u.ID_Usuario
        JOIN Miembro_Grupo mg ON g.ID_Grupo = mg.ID_Grupo
        WHERE mg.ID_Usuario = %s AND mg.Confirmado = 1
        """
        cursor.execute(query_grupos, (user_id, user_id))
        grupos = cursor.fetchall()
    except Exception as e:
        return jsonify({"error": f"Error al obtener los grupos: {str(e)}"}), 500
    finally:
        cursor.close()
        connection.close()

    return jsonify(grupos), 200

@app.route('/api/grupo/<int:grupo_id>', methods=['GET'])
@jwt_required()
def obtener_info_grupo(grupo_id):
    user_id = get_jwt_identity()

    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Verificar si el usuario pertenece al grupo
        query_verificar = """
        SELECT Confirmado 
        FROM Miembro_Grupo 
        WHERE ID_Usuario = %s AND ID_Grupo = %s AND Confirmado = 1
        """
        cursor.execute(query_verificar, (user_id, grupo_id))
        miembro = cursor.fetchone()

        if not miembro:
            return jsonify({"error": "No tienes acceso a este grupo"}), 403

        # Obtener información del grupo
        query_grupo = """
        SELECT g.ID_Grupo, g.Nombre_Grupo, g.Descripcion, 
               CONCAT(u.Nombre, ' ', u.Apellido_P, ' ', u.Apellido_M) AS Nombre_Admin,
               g.Codigo_Invitacion, g.ID_Admin
        FROM Grupo g
        JOIN Usuario u ON g.ID_Admin = u.ID_Usuario
        WHERE g.ID_Grupo = %s
        """
        cursor.execute(query_grupo, (grupo_id,))
        grupo_info = cursor.fetchone()

        if not grupo_info:
            return jsonify({"error": "Grupo no encontrado"}), 404

        # Obtener miembros del grupo
        query_miembros = """
        SELECT u.ID_Usuario, 
            CONCAT(u.Nombre, ' ', u.Apellido_P, ' ', u.Apellido_M) AS Nombre_Completo, 
            mg.Email, 
            mg.Confirmado
        FROM Miembro_Grupo mg
        LEFT JOIN Usuario u ON mg.ID_Usuario = u.ID_Usuario
        WHERE mg.ID_Grupo = %s
        """
        cursor.execute(query_miembros, (grupo_id,))
        miembros = cursor.fetchall()
        grupo_info['Miembros'] = miembros

        # Obtener metas grupales asociadas
        query_metas = """
        SELECT ID_Ahorro_Grupal, Descripcion, Monto_Objetivo, Monto_Actual, Fecha_Inicio, Fecha_Limite
        FROM Meta_Ahorro_Grupal
        WHERE ID_Grupo = %s
        """
        cursor.execute(query_metas, (grupo_id,))
        metas = cursor.fetchall()

        grupo_info['Metas'] = metas

        return jsonify(grupo_info), 200

    except Exception as e:
        return jsonify({"error": f"Error al obtener información del grupo: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()

@app.route('/api/grupo/<int:grupo_id>/info', methods=['GET'])
@jwt_required()
def obtener_info_basica_grupo(grupo_id):
    """
    Endpoint para obtener información básica de un grupo (nombre y descripción) 
    y verificar si el usuario pertenece al grupo.
    """
    user_id = get_jwt_identity()  # Obtener el ID del usuario autenticado

    connection = create_connection()  # Crear conexión a la base de datos
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Verificar si el usuario pertenece al grupo y está confirmado
        query_verificar = """
        SELECT Confirmado 
        FROM Miembro_Grupo 
        WHERE ID_Usuario = %s AND ID_Grupo = %s AND Confirmado = 1
        """
        cursor.execute(query_verificar, (user_id, grupo_id))
        miembro = cursor.fetchone()

        if not miembro:
            return jsonify({"error": "No tienes acceso a este grupo"}), 403

        # Obtener información básica del grupo
        query_grupo = """
        SELECT Nombre_Grupo, Descripcion
        FROM Grupo
        WHERE ID_Grupo = %s
        """
        cursor.execute(query_grupo, (grupo_id,))
        grupo_info = cursor.fetchone()

        if not grupo_info:
            return jsonify({"error": "Grupo no encontrado"}), 404

        return jsonify(grupo_info), 200

    except Exception as e:
        return jsonify({"error": f"Error al obtener información del grupo: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()

@app.route('/api/grupo/<int:grupo_id>/gastos', methods=['GET'])
@jwt_required()
def obtener_gastos_grupo(grupo_id):
    """
    Endpoint para obtener los gastos de un grupo específico.
    """
    user_id = get_jwt_identity()  # Obtener el ID del usuario autenticado

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Verificar si el usuario pertenece al grupo y está confirmado
        query_verificar = """
        SELECT Confirmado 
        FROM Miembro_Grupo 
        WHERE ID_Usuario = %s AND ID_Grupo = %s AND Confirmado = 1
        """
        cursor.execute(query_verificar, (user_id, grupo_id))
        miembro = cursor.fetchone()

        if not miembro:
            return jsonify({"error": "No tienes acceso a este grupo"}), 403

        # Obtener los gastos del grupo junto con el nombre del responsable
        query_gastos = """
        SELECT g.ID_Gasto_Grupal, g.Descripcion, g.Monto, g.Fecha, 
               COALESCE(u1.Nombre_Completo, u2.Nombre_Completo, 'Pendiente') AS Responsable,
               g.Estado
        FROM Gasto_Grupal g
        LEFT JOIN (
            SELECT ID_Usuario, CONCAT(Nombre, ' ', Apellido_P, ' ', Apellido_M) AS Nombre_Completo
            FROM Usuario
        ) u1 ON g.ID_Usuario = u1.ID_Usuario
        LEFT JOIN (
            SELECT ID_Usuario, CONCAT(Nombre, ' ', Apellido_P, ' ', Apellido_M) AS Nombre_Completo
            FROM Usuario
        ) u2 ON g.Asignado_A = u2.ID_Usuario
        WHERE g.ID_Grupo = %s
        ORDER BY g.Fecha DESC
        """
        cursor.execute(query_gastos, (grupo_id,))
        gastos = cursor.fetchall()

        # Validar y formatear las fechas para JSON
        for gasto in gastos:
            if gasto['Fecha']:
                gasto['Fecha'] = gasto['Fecha'].strftime('%Y-%m-%d')
            else:
                gasto['Fecha'] = None

        return jsonify(gastos), 200

    except Exception as e:
        return jsonify({"error": f"Error al obtener los gastos del grupo: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()


@app.route('/api/grupo/<int:grupo_id>/gastos/filtrados', methods=['POST'])
@jwt_required()
def obtener_gastos_grupales_filtrados(grupo_id):
    """
    Endpoint para obtener datos de los gastos grupales filtrados, agrupados por descripción
    para construir una gráfica de pastel.
    """
    user_id = get_jwt_identity()  # Obtener el ID del usuario autenticado
    data = request.json
    estado = data.get('estado', None)
    asignado_a = data.get('asignado_a', None)
    fecha_inicio = data.get('fecha_inicio', None)
    fecha_fin = data.get('fecha_fin', None)

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Verificar si el usuario pertenece al grupo y está confirmado
        query_verificar = """
        SELECT Confirmado 
        FROM Miembro_Grupo 
        WHERE ID_Usuario = %s AND ID_Grupo = %s AND Confirmado = 1
        """
        cursor.execute(query_verificar, (user_id, grupo_id))
        miembro = cursor.fetchone()

        if not miembro:
            return jsonify({"error": "No tienes acceso a este grupo"}), 403

        # Construir la consulta SQL para filtrar los gastos grupales
        query = """
        SELECT Descripcion, SUM(Monto) as Monto
        FROM Gasto_Grupal
        WHERE ID_Grupo = %s
        """
        params = [grupo_id]

        if estado:
            query += " AND Estado = %s"
            params.append(estado)

        if asignado_a:
            query += " AND Asignado_A = %s"
            params.append(asignado_a)

        if fecha_inicio and fecha_fin:
            query += " AND Fecha BETWEEN %s AND %s"
            params.append(fecha_inicio)
            params.append(fecha_fin)

        query += " GROUP BY Descripcion"

        cursor.execute(query, params)
        gastos_filtrados = cursor.fetchall()

        connection.close()

        return jsonify(gastos_filtrados), 200

    except Exception as e:
        return jsonify({"error": f"Error al obtener los gastos filtrados del grupo: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()


@app.route('/api/grupo/<int:grupo_id>/registrar-gasto', methods=['POST'])
@jwt_required()
def registrar_gasto_grupal(grupo_id):
    """
    Endpoint para registrar un gasto grupal.
    """
    user_id = get_jwt_identity()  # Obtener el ID del usuario autenticado
    data = request.json

    descripcion = data.get('descripcion')
    monto = data.get('monto')
    fecha = data.get('fecha')
    asignado_a = data.get('asignado_a', None)  # ID del usuario asignado
    es_mi_gasto = data.get('es_mi_gasto', False)  # Checkbox para "Es mi gasto"

    if not descripcion or not monto or not fecha:
        return jsonify({"error": "Faltan datos requeridos (descripción, monto o fecha)."}), 400

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor(dictionary=True)

    try:
        # Verificar si el usuario pertenece al grupo y está confirmado
        query_verificar = """
        SELECT ID_Usuario, ID_Grupo, Confirmado, 
               CASE WHEN ID_Usuario = (SELECT ID_Admin FROM Grupo WHERE ID_Grupo = %s) THEN 1 ELSE 0 END AS es_admin
        FROM Miembro_Grupo
        WHERE ID_Usuario = %s AND ID_Grupo = %s AND Confirmado = 1
        """
        cursor.execute(query_verificar, (grupo_id, user_id, grupo_id))
        miembro = cursor.fetchone()

        if not miembro:
            return jsonify({"error": "No tienes acceso a este grupo o no estás confirmado."}), 403

        es_admin = miembro['es_admin']

        # Determinar el comportamiento basado en si es administrador o no
        if es_admin and not es_mi_gasto:
            # Administrador asignando un gasto
            if not asignado_a and asignado_a != "cualquiera":
                return jsonify({"error": "Debes asignar el gasto o elegir 'cualquiera'."}), 400

            estado = "Pendiente" if asignado_a != "cualquiera" else "Pendiente"
            asignado_a = None if asignado_a == "cualquiera" else asignado_a

            query_insert = """
            INSERT INTO Gasto_Grupal (Descripcion, Monto, Fecha, ID_Grupo, Asignado_A, Estado)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (descripcion, monto, fecha, grupo_id, asignado_a, estado))

        else:
            # Miembro registrando su propio gasto o administrador seleccionando "Es mi gasto"
            estado = "Pagado"
            query_insert = """
            INSERT INTO Gasto_Grupal (Descripcion, Monto, Fecha, ID_Grupo, ID_Usuario, Estado)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query_insert, (descripcion, monto, fecha, grupo_id, user_id, estado))

        connection.commit()

        return jsonify({"message": "Gasto registrado con éxito."}), 201

    except Exception as e:
        connection.rollback()
        return jsonify({"error": f"Error al registrar el gasto grupal: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
