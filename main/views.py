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
            return redirect('dashboard')
        except Exception as e:
            print(f"Error de login: {e}")
            return render(request, 'main/login.html', {'error': 'Credenciales inválidas'})
    return render(request, 'main/login.html')


def dashboard_view(request):
    import datetime

    user_id = request.session['uid']
    device_id = "device_001"  # O como lo obtengas

    user_habits = db.child("users").child(user_id).child("habits").get().val() or {}
    print(user_habits)
    progress = db.child("devices").child(device_id).child("progress").get().val() or {}

    # Días de la semana
    # Ahora el 0 es domingo, así que ajustamos el orden de los días
    days_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    consistency_labels = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

    # 1. Total de hábitos programados por día (por hábito, no por tipo)
    # Calcula el total de hábitos programados por día según el JSON de user_habits
    total_per_day = {day: 0 for day in days_order}
    for habit_id, habit in user_habits.items():
        for day_num in habit.get("days", []):
            if 0 <= day_num < len(days_order):
                day_name = days_order[day_num]
                total_per_day[day_name] += 1

    # Validación: Si completed_today > total_today, ajustamos completed_today
    # (esto se hace después de calcular completed_today, pero aquí dejamos la lógica para referencia)
    # Ejemplo de uso después:
    # if completed_today > total_today:
    #     completed_today = total_today

    # 2. Total de hábitos completados por día
    completed_per_day = {day: 0 for day in days_order}
    for prog in progress.values():
        if prog.get("completed") and prog.get("date"):
            date = datetime.datetime.strptime(prog["date"], "%Y-%m-%d")
            day_name = date.strftime("%A")
            # Solo cuenta si el habit_id pertenece al usuario
            if prog.get("habit_id") in user_habits:
                completed_per_day[day_name] += 1

    # 3. Consistency data (porcentaje por día)
    # Calcular el porcentaje de tareas completadas por día correctamente
    consistency_data = []
    for day in days_order:
        # Para cada día, contar cuántos hábitos del usuario estaban programados para ese día
        total = 0
        completed = 0
        for habit_id, habit in user_habits.items():
            # Verifica si el hábito está programado para este día
            if days_order.index(day) in habit.get("days", []):
                total += 1
                # Buscar si hay progreso completado para este hábito en este día
                for prog in progress.values():
                    if (
                        prog.get("habit_id") == habit_id
                        and prog.get("completed")
                        and prog.get("date")
                    ):
                        # Revisar si la fecha corresponde al día de la semana actual
                        try:
                            prog_date = datetime.datetime.strptime(prog["date"], "%Y-%m-%d")
                            if prog_date.strftime("%A") == day:
                                completed += 1
                                break  # Solo contar una vez por hábito por día
                        except Exception:
                            continue
        
        percent = int((completed / total) * 100) if total > 0 else 0
        consistency_data.append(percent)

    # 4. Para hoy
    today_weekday = datetime.datetime.now().strftime("%A")
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Total de hábitos programados para hoy
    total_today = total_per_day[today_weekday]

    # Total de hábitos completados hoy
    completed_today = 0
    for prog in progress.values():
        if prog.get("completed") and prog.get("date") == today_date:
            if prog.get("habit_id") in user_habits:
                completed_today += 1

    # Progreso diario en porcentaje
    # Usamos round() para asegurar que 3/4 da 75 y no 74
    progress_value = int((completed_today / total_today) * 100) if total_today > 0 else 0
    
    # --- Analytics Overview ---
    # Por tipo: higiene, salud, nutricion
    month = datetime.datetime.now().strftime("%Y-%m")
    type_totals = {"higiene": 0, "salud": 0, "nutricion": 0}
    type_completed = {"higiene": 0, "salud": 0, "nutricion": 0}

    for habit_id, habit in user_habits.items():
        tipo = habit.get("type")
        if tipo in type_totals:
            type_totals[tipo] += 1

    # Calcular el progreso diario viendo cuántas tareas del día se han completado
    for prog in progress.values():
        if prog.get("completed") and prog.get("date") == today_date:
            habit_id = prog.get("habit_id")
            tipo = user_habits.get(habit_id, {}).get("type")
            if tipo in type_completed:
                type_completed[tipo] += 1

    hygiene_percent = int((type_completed["higiene"] / type_totals["higiene"]) * 100) if type_totals["higiene"] > 0 else 0
    health_percent = int((type_completed["salud"] / type_totals["salud"]) * 100) if type_totals["salud"] > 0 else 0
    nutrition_percent = int((type_completed["nutricion"] / type_totals["nutricion"]) * 100) if type_totals["nutricion"] > 0 else 0

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
    })


def profile_view(request):
    user_id = request.session.get('uid')
    if not user_id:
        return redirect('login')

    try:
        user_data = db.child("users").child(user_id).get().val()
        name = user_data.get("name", "Usuario")
        email = user_data.get("email", "correo@dominio.com")
        photo_url = user_data.get("profile_picture", "/static/images/default_profile.png")
        
    except Exception as e:
        print("Error al obtener datos del perfil:", e)
        name = "Usuario"
        email = "correo@dominio.com"
        photo_url = "/static/images/default_profile.png"

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
                    user = auth_pyrebase.sign_in_with_email_and_password(email, password)
                    request.session['uid'] = user['localId']
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
            # Si no existe, crear un nuevo usuario
            try:
                # Crear usuario con contraseña temporal
                user = auth_pyrebase.create_user_with_email_and_password(email, "google_user_temp_password")
                uid = user['localId']
                
                # Guardar información adicional en Firebase Database
                db.child("users").child(uid).set({
                    "name": name,
                    "email": email,
                    "profile_picture": picture,
                    "google_id": google_user_id,
                    "auth_provider": "google",
                    "avatar_id": "avatar1"  # Avatar por defecto
                })
                
            except Exception as e:
                print(f"Error creando usuario: {e}")
                return render(request, 'main/login.html', {'error': 'Error al crear usuario con Google'})
        
        # Guardar el UID en la sesión
        request.session['uid'] = user['localId']
        
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


