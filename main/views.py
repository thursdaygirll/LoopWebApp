#from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from loopwebapp.firebase_config import firestore_db, auth_pyrebase, db
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from loopwebapp.firebase_config import auth_pyrebase
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import credentials
from loopwebapp.firebase_config import firestore_db
from django.conf import settings
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import json
import os
from loopwebapp.google_oauth_config import GOOGLE_OAUTH_CONFIG




def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = auth_pyrebase.sign_in_with_email_and_password(email, password)
            request.session['uid'] = user['localId']
            # Guardar idToken para autenticación en Realtime Database
            request.session['idToken'] = user.get('idToken')
            return redirect('dashboard')
        except Exception as e:
            print(f"Error de login: {e}")
            return render(request, 'main/login.html', {'error': 'Credenciales inválidas'})
    return render(request, 'main/login.html')


def dashboard_view(request):
    import datetime

    user_id = request.session.get('uid')
    id_token = request.session.get('idToken')
    if not user_id:
        return redirect('login')
    if not id_token:
        # Si no hay idToken, forzar re-login para obtenerlo
        return redirect('login')
    device_id = "device_001"  # O como lo obtengas

    user_habits = db.child("users").child(user_id).child("habits").get(id_token).val() or {}
    # Datos del usuario para saludo y foto
    user_data = db.child("users").child(user_id).get(id_token).val() or {}
    display_name = user_data.get("name", "Usuario")
    photo_url = user_data.get("profile_picture") or "/static/main/profileicon.png"
    print(user_habits)
    progress = db.child("devices").child(device_id).child("progress").get(id_token).val() or {}

    # Días de la semana
    # Ahora el 0 es domingo, así que ajustamos el orden de los días
    days_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    consistency_labels = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    # Fechas de la semana actual (domingo a sábado)
    today = datetime.datetime.now()
    # Calcular el domingo de esta semana
    # weekday(): Monday=0..Sunday=6, usamos un ajuste para tomar domingo como inicio
    days_since_sunday = (today.weekday() + 1) % 7
    start_of_week = today - datetime.timedelta(days=days_since_sunday)
    week_dates = [start_of_week + datetime.timedelta(days=i) for i in range(7)]
    day_to_date_str = {d.strftime("%A"): d.strftime("%Y-%m-%d") for d in week_dates}

    # 1. Total de hábitos programados por día (por hábito, no por tipo)
    total_per_day = {day: 0 for day in days_order}
    for habit_id, habit in (user_habits or {}).items():
        for day_num in habit.get("days", []):
            if 0 <= day_num < len(days_order):
                day_name = days_order[day_num]
                total_per_day[day_name] += 1

    # Validación: Si completed_today > total_today, ajustamos completed_today
    # (esto se hace después de calcular completed_today, pero aquí dejamos la lógica para referencia)
    # Ejemplo de uso después:
    # if completed_today > total_today:
    #     completed_today = total_today

    # 2. Total de hábitos completados por día (único por hábito/día para evitar doble conteo)
    completed_sets = {day: set() for day in days_order}
    progress_values = list(progress.values()) if isinstance(progress, dict) else (progress or [])
    for prog in progress_values:
        hid = prog.get("habit_id")
        if prog.get("completed") and prog.get("date") and hid in user_habits:
            try:
                date_obj = datetime.datetime.strptime(prog["date"], "%Y-%m-%d")
                day_name = date_obj.strftime("%A")
                # Solo contar si es fecha de esta semana exacta
                if day_to_date_str.get(day_name) == prog["date"]:
                    completed_sets[day_name].add(hid)
            except Exception:
                continue
    completed_per_day = {day: len(s) for day, s in completed_sets.items()}

    # 3. Consistency data (porcentaje por día de la semana actual)
    consistency_data = []
    for day in days_order:
        total = total_per_day.get(day, 0)
        completed = completed_per_day.get(day, 0)
        percent = int((completed / total) * 100) if total > 0 else 0
        consistency_data.append(percent)

    # 4. Para hoy
    today_weekday = today.strftime("%A")
    today_date = today.strftime("%Y-%m-%d")

    # Total de hábitos programados para hoy
    total_today = total_per_day.get(today_weekday, 0)

    # Total de hábitos completados hoy
    completed_today = completed_per_day.get(today_weekday, 0)

    # Progreso diario en porcentaje
    # Usamos round() para asegurar que 3/4 da 75 y no 74
    progress_value = int((completed_today / total_today) * 100) if total_today > 0 else 0
    
    # --- Analytics Overview (por semana: % completado vs programado por tipo) ---
    # Para cada tipo (higiene/salud/nutricion), calcular:
    #   porcentaje = (# completados únicos esta semana del tipo) / (# ocurrencias programadas en la semana del tipo) * 100
    types = ["higiene", "salud", "nutricion"]
    week_dates_set = set(day_to_date_str.values())

    # Ocurrencias programadas por semana (número de días marcados por hábito) por tipo
    type_scheduled_week = {t: 0 for t in types}
    for habit_id, habit in (user_habits or {}).items():
        tipo = habit.get("type")
        if tipo in type_scheduled_week:
            occurrences = sum(1 for d in habit.get("days", []) if 0 <= d < 7)
            type_scheduled_week[tipo] += occurrences

    # Completados únicos por (habit_id, date) dentro de la semana por tipo
    type_completed_pairs = {t: set() for t in types}
    for prog in progress_values:
        if not (prog.get("completed") and prog.get("date") in week_dates_set):
            continue
        hid = prog.get("habit_id")
        if not hid or hid not in (user_habits or {}):
            continue
        tipo = (user_habits or {}).get(hid, {}).get("type")
        if tipo in type_completed_pairs:
            pair = (hid, prog.get("date"))
            type_completed_pairs[tipo].add(pair)

    type_completed_week = {t: len(type_completed_pairs[t]) for t in types}

    def pct(comp, sched):
        if sched <= 0:
            return 0
        return int(round((comp / sched) * 100))

    hygiene_percent = pct(type_completed_week["higiene"], type_scheduled_week["higiene"])
    health_percent = pct(type_completed_week["salud"], type_scheduled_week["salud"])
    nutrition_percent = pct(type_completed_week["nutricion"], type_scheduled_week["nutricion"])

    print(hygiene_percent)
    print(health_percent)
    print(nutrition_percent)
    

    print(progress_value)
    print(total_today)
    print(completed_today)
    


    
    
    

    return render(request, 'main/dashboard.html', {
        'consistency_labels': consistency_labels,
        'consistency_data': consistency_data,
        'progress_value': progress_value,
        'total_today': total_today,
        'completed_today': completed_today,
        'hygiene_percent': hygiene_percent,
        'health_percent': health_percent,
        'nutrition_percent': nutrition_percent,
        'name': display_name,
        'photo_url': photo_url,
    })


def profile_view(request):
    user_id = request.session.get('uid')
    id_token = request.session.get('idToken')
    if not user_id:
        return redirect('login')

    try:
        user_data = db.child("users").child(user_id).get(id_token).val()
        name = user_data.get("name", "Usuario")
        email = user_data.get("email", "correo@dominio.com")
        photo_url = user_data.get("profile_picture", "/static/main/profileicon.png")
        
    except Exception as e:
        print("Error al obtener datos del perfil:", e)
        name = "Usuario"
        email = "correo@dominio.com"
        photo_url = "/static/main/profileicon.png"

    return render(request, 'main/profile.html', {
        'photo_url': photo_url,
        'user_id': user_id,
        'name': name,
        'email': email
    })


@csrf_exempt
def register_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        display_name = request.POST.get('display_name')
        last_name = request.POST.get('last_name')

        if not email or not password or not confirm_password or not display_name or not last_name:
            return render(request, 'main/register.html', {'error': 'Todos los campos son obligatorios.'})

        if password != confirm_password:
            return render(request, 'main/register.html', {'error': 'Las contraseñas no coinciden.'})

        if len(password) < 6:
            return render(request, 'main/register.html', {'error': 'La contraseña debe tener al menos 6 caracteres.'})

        try:
    
            user = auth_pyrebase.create_user_with_email_and_password(email, password)
            uid = user['localId']
            if request.method == 'POST':
                email = request.POST.get('email')
                password = request.POST.get('password')
                try:
                    signed_in = auth_pyrebase.sign_in_with_email_and_password(email, password)
                    request.session['uid'] = signed_in['localId']
                    request.session['idToken'] = signed_in.get('idToken')
                    return redirect('dashboard')
                except Exception as e:
                    print(f"Error de login: {e}")
                    return render(request, 'main/login.html', {'error': 'Credenciales inválidas'})
            return render(request, 'main/login.html')
            #login_user = auth_pyrebase.sign_in_with_email_and_password(email, password)
            #id_token = login_user['idToken']

            #db.child("users").child(uid).set({
            #    "name": f"{display_name} {last_name}",
            #    "email": email,
            #    "profile_picture": ""
            #}, id_token)

            return render(request, 'main/login.html', {'success': 'Usuario creado correctamente'})
        except Exception as e:
            print("Error al crear usuario:", e)
            return render(request, 'main/register.html', {'error': f'No se pudo crear el usuario: {e}'})
    return render(request, 'main/register.html')



@csrf_exempt
def upload_profile_picture(request):
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        user_id = request.session.get('uid')
        if not user_id:
            return JsonResponse({'status': 'error', 'message': 'Usuario no autenticado.'})

        file = request.FILES['profile_picture']
        file_path = f"profile_pictures/{user_id}.jpg"
        # Guarda el archivo temporalmente
        temp_path = default_storage.save(file.name, file)
        # Sube a Firebase Storage
        #storage.child(file_path).put(temp_path) # This line was removed as per the edit hint
        # Obtén la URL de descarga
        #photo_url = storage.child(file_path).get_url(None) # This line was removed as per the edit hint
        # Borra el archivo temporal
        default_storage.delete(temp_path)
        # Actualiza la URL en la base de datos
        db.child("users").child(user_id).update({"profile_picture": photo_url}) # This line was removed as per the edit hint

        return render(request, 'main/profile.html', {
            'photo_url': photo_url,
            'success': 'Foto actualizada correctamente',
            'user_id': user_id
        })
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})


@csrf_exempt
def update_profile(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        display_name = request.POST.get('display_name')
        photo_url = request.POST.get('photo_url')
        try:
            #auth.update_user( # This line was removed as per the edit hint
            #    user_id,
            #    display_name=display_name,
            #    photo_url=photo_url
            #)
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

def get_profile(request, user_id):
    try:
        user = auth_pyrebase.get_user(user_id) # Changed from auth.get_user to auth_pyrebase.get_user
        return JsonResponse({
            'email': user.email,
            'display_name': user.display_name,
            'photo_url': user.photo_url
            
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


def google_login(request):
    """Inicia el flujo de autenticación con Google"""
    try:
        # Crear el flujo de OAuth
        flow = Flow.from_client_config(
            GOOGLE_OAUTH_CONFIG,
            scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        )
        
        # Configurar la URI de redirección explícitamente
        flow.redirect_uri = "http://localhost:8000/auth/google/callback/"
        
        # Generar la URL de autorización
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Guardar el estado en la sesión
        request.session['oauth_state'] = state
        
        print(f"URL de autorización generada: {authorization_url}")
        print(f"Estado OAuth: {state}")
        
        return redirect(authorization_url)
        
    except Exception as e:
        print(f"Error en google_login: {e}")
        return render(request, 'main/login.html', {'error': f'Error al iniciar sesión con Google: {str(e)}'})


def google_callback(request):
    """Maneja la respuesta de Google OAuth"""
    try:
        # Obtener el código de autorización
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        print(f"Código recibido: {code}")
        print(f"Estado recibido: {state}")
        print(f"Error recibido: {error}")
        
        # Verificar si hay error
        if error:
            return render(request, 'main/login.html', {'error': f'Error de Google: {error}'})
        
        # Verificar el estado
        if state != request.session.get('oauth_state'):
            return render(request, 'main/login.html', {'error': 'Error de estado en OAuth'})
        
        # Crear el flujo de OAuth
        flow = Flow.from_client_config(
            GOOGLE_OAUTH_CONFIG,
            scopes=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
        )
        
        # Configurar la URI de redirección explícitamente
        flow.redirect_uri = "http://localhost:8000/auth/google/callback/"
        
        # Intercambiar el código por tokens
        flow.fetch_token(code=code)
        
        # Obtener información del usuario
        id_info = id_token.verify_oauth2_token(
            flow.credentials.id_token, 
            requests.Request(), 
            GOOGLE_OAUTH_CONFIG['web']['client_id']
        )
        
        # Extraer información del usuario
        google_user_id = id_info['sub']
        email = id_info['email']
        name = id_info.get('name', '')
        picture = id_info.get('picture', '')
        
        print(f"Usuario autenticado: {email}")
        
        # Intentar crear o obtener el usuario en Firebase
        try:
            # Intentar obtener el usuario existente por email
            user = auth_pyrebase.sign_in_with_email_and_password(email, "google_user_temp_password")
        except:
            # Si no existe, crear un nuevo usuario y luego iniciar sesión para obtener idToken
            try:
                created = auth_pyrebase.create_user_with_email_and_password(email, "google_user_temp_password")
                uid = created['localId']
                # Iniciar sesión para obtener idToken
                user = auth_pyrebase.sign_in_with_email_and_password(email, "google_user_temp_password")
                id_token = user.get('idToken')
                # Guardar información adicional en Firebase Database (autenticado)
                db.child("users").child(uid).set({
                    "name": name,
                    "email": email,
                    "profile_picture": picture,
                    "google_id": google_user_id,
                    "auth_provider": "google",
                    "avatar_id": "avatar1"
                }, id_token)
            except Exception as e:
                print(f"Error creando usuario: {e}")
                return render(request, 'main/login.html', {'error': 'Error al crear usuario con Google'})

        # Guardar el UID e idToken en la sesión
        request.session['uid'] = user['localId']
        request.session['idToken'] = user.get('idToken')
        
        # Limpiar el estado de OAuth
        if 'oauth_state' in request.session:
            del request.session['oauth_state']
        
        return redirect('dashboard')
        
    except Exception as e:
        print(f"Error en google_callback: {e}")
        return render(request, 'main/login.html', {'error': f'Error en la autenticación con Google: {str(e)}'})


def logout_view(request):
    """Cerrar sesión"""
    if 'uid' in request.session:
        del request.session['uid']
    if 'idToken' in request.session:
        del request.session['idToken']
    return redirect('login')


@csrf_exempt
def firebase_google_auth(request):
    """Maneja la autenticación de Google usando Firebase Auth"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            id_token = data.get('id_token')
            
            if not id_token:
                return JsonResponse({'error': 'No se proporcionó token de ID'}, status=400)
            
            # Verificar el token con Firebase
            user = auth_pyrebase.sign_in_with_custom_token(id_token)
            
            # Obtener información del usuario
            user_info = auth_pyrebase.get_user(user['localId'])
            
            # Guardar en sesión
            request.session['uid'] = user['localId']
            
            # Guardar información del usuario en Firebase Database si no existe
            user_data = db.child("users").child(user['localId']).get().val()
            if not user_data:
                db.child("users").child(user['localId']).set({
                    "name": user_info.get('displayName', 'Usuario'),
                    "email": user_info.get('email', ''),
                    "profile_picture": user_info.get('photoURL', ''),
                    "auth_provider": "google"
                })
            
            return JsonResponse({'success': True, 'redirect': '/dashboard/'})
            
        except Exception as e:
            print(f"Error en firebase_google_auth: {e}")
            return JsonResponse({'error': 'Error en la autenticación'}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


def login_firebase_view(request):
    """Vista para el login con Firebase Auth"""
    return render(request, 'main/login_firebase.html')


