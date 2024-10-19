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

        # Verificar si el usuario tiene ingresos registrados
        query_income = """
        SELECT ID_Ingreso, Descripcion, Monto, Fecha, Periodicidad, EsFijo 
        FROM Ingreso 
        WHERE ID_Usuario = %s
        """
        cursor.execute(query_income, (user_id,))
        incomes = cursor.fetchall()

        if incomes:
            mostrar_tab_periodo = False
            descripcion = None
            fecha_ultimo_ingreso = None

            # Establecer hasIncome en True porque ya tiene ingresos registrados
            hasIncome = True
            print(f"El usuario tiene {len(incomes)} ingresos registrados.")

            # Agrupar ingresos no fijos por descripción y seleccionar el más reciente
            ingresos_no_fijos = {}
            for income in incomes:
                if income['EsFijo'] == 0:
                    descripcion = income['Descripcion']
                    if descripcion not in ingresos_no_fijos or income['Fecha'] > ingresos_no_fijos[descripcion]['Fecha']:
                        ingresos_no_fijos[descripcion] = income

            # Verificar si hay ingresos no fijos registrados
            if not ingresos_no_fijos:
                connection.close()
                print("No tiene ingresos no fijos, no se mostrará ninguna ventana flotante.")
                return jsonify({
                    "message": "Login exitoso",
                    "token": access_token,  # Retornar el token en la respuesta
                    "user": user,
                    "hasIncome": hasIncome,
                    "showFloatingTabIncome": False,
                    "showFloatingTab": False
                }), 200

            # Verificar cada ingreso no fijo para determinar si se debe mostrar la ventana flotante de periodicidad
            for descripcion, income in ingresos_no_fijos.items():
                fecha_ultimo_ingreso = income['Fecha']
                periodicidad = income['Periodicidad']

                print(f"Fecha del último ingreso para {descripcion}: {fecha_ultimo_ingreso}")
                print(f"Periodicidad: {periodicidad}")
                    
                # Determinar la fecha de comparación en base a la periodicidad
                if periodicidad == 'Diario':
                    fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(days=1)
                elif periodicidad == 'Semanal':
                    fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=1)
                elif periodicidad == 'Quincenal':
                    fecha_siguiente_ingreso = fecha_ultimo_ingreso + timedelta(weeks=2)
                elif periodicidad == 'Mensual':
                    fecha_siguiente_ingreso = fecha_ultimo_ingreso + relativedelta(months=1)

                fecha_actual = datetime.now().date()
                print(f"Fecha actual: {fecha_actual}")
                print(f"Fecha siguiente ingreso para {descripcion}: {fecha_siguiente_ingreso}")

                if fecha_actual >= fecha_siguiente_ingreso:
                    mostrar_tab_periodo = True
                    break  # Si se debe mostrar la ventana de periodo, no es necesario seguir iterando

            connection.close()

            if mostrar_tab_periodo:
                print("Mostrar ventana flotante para actualizar ingreso según el periodo.")
                return jsonify({
                    "message": "Login exitoso",
                    "token": access_token,  # Retornar el token en la respuesta
                    "user": user,
                    "hasIncome": hasIncome,  # Indicar que tiene ingresos
                    "showFloatingTabIncome": True,
                    "descripcionIngreso": descripcion,
                    "fechaUltimoIngreso": fecha_ultimo_ingreso.strftime('%d/%m/%Y')
                }), 200
            else:
                print("No se mostrará ninguna ventana flotante.")
                return jsonify({
                    "message": "Login exitoso",
                    "token": access_token,  # Retornar el token en la respuesta
                    "user": user,
                    "hasIncome": hasIncome,  # Indicar que tiene ingresos
                    "showFloatingTabIncome": False,
                    "showFloatingTab": False  # No mostrar la tab de captura inicial si ya tiene ingresos
                }), 200
        else:
            # Si no tiene ningún ingreso registrado, se debe mostrar la ventana para capturar ingresos iniciales
            hasIncome = False
            connection.close()
            print("No tiene ingresos registrados, mostrar ventana para capturar ingresos iniciales.")
            return jsonify({
                "message": "Login exitoso",
                "token": access_token,  # Retornar el token en la respuesta
                "user": user,
                "hasIncome": hasIncome,  # Indicar que no tiene ingresos
                "showFloatingTabIncome": False,
                "showFloatingTab": True  # Mostrar la ventana para capturar los ingresos iniciales
            }), 200
    else:
        connection.close()
        print("Correo o contraseña incorrectos.")
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
    id_usuario = get_jwt_identity()  # Obtener el ID del usuario desde el token JWT

    descripcion = data.get('descripcion')
    monto = data.get('monto')
    fecha = data.get('fecha', None)
    categoria = data.get('categoria')
    periodico = data.get('periodico', False)
    id_grupo = data.get('id_grupo', None)

    # Verificar si se envió una fecha en el payload; si no, usar la fecha actual
    if fecha:
        try:
            fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({"error": "Formato de fecha incorrecto. Use YYYY-MM-DD."}), 400
    else:
        fecha = datetime.now().date()

    # Verificar datos obligatorios
    if not descripcion or not monto or not categoria:
        return jsonify({"error": "Datos incompletos"}), 400

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Insertar el nuevo gasto
    query = """
    INSERT INTO Gasto (Descripcion, Monto, Fecha, Categoria, Periodico, ID_Usuario, ID_Grupo)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (descripcion, monto, fecha, categoria, periodico, id_usuario, id_grupo))

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

    cursor = connection.cursor()

    # Obtener los gastos del usuario
    query = """
    SELECT ID_Gasto, Descripcion, Monto, Fecha, Categoria, Periodico, ID_Grupo
    FROM Gasto
    WHERE ID_Usuario = %s
    ORDER BY Fecha DESC
    """
    cursor.execute(query, (id_usuario,))
    gastos = cursor.fetchall()

    connection.close()

    # Convertir el resultado en formato JSON
    gastos_json = [
        {
            "ID_Gasto": gasto[0],
            "Descripcion": gasto[1],
            "Monto": gasto[2],
            "Fecha": gasto[3],
            "Categoria": gasto[4],
            "Periodico": gasto[5],
            "ID_Grupo": gasto[6],
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
    id_grupo = data.get('id_grupo', None)
    fecha_inicio = data.get('fecha_inicio', None)
    fecha_fin = data.get('fecha_fin', None)

    # Conexión a la base de datos
    connection = create_connection()
    if connection is None:
        return jsonify({"error": "Error al conectar a la base de datos"}), 500

    cursor = connection.cursor()

    # Construir la consulta de filtrado dinámico
    query = """
    SELECT ID_Gasto, Descripcion, Monto, Fecha, Categoria, Periodico, ID_Grupo
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
    
    if id_grupo:
        query += " AND ID_Grupo = %s"
        query_params.append(id_grupo)

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
            "Fecha": gasto[3],
            "Categoria": gasto[4],
            "Periodico": gasto[5],
            "ID_Grupo": gasto[6],
        }
        for gasto in gastos
    ]

    return jsonify(gastos_json), 200




if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)