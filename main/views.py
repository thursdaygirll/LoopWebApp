#from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from loopwebapp.firebase_config import auth, storage, db
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from loopwebapp.firebase_config import auth_pyrebase
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import credentials




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
    if 'uid' not in request.session:
        return redirect('login')
    # Datos de ejemplo para las gráficas
    consistency_labels = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    consistency_data = [80, 90, 70, 85, 95, 60, 75]
    progress_labels = ['Semana 1', 'Semana 2', 'Semana 3', 'Semana 4']
    progress_data = [60, 75, 80, 90]
    progress_value = 70  # O el valor que calcules dinámicamente
    return render(request, 'main/dashboard.html', {
        'consistency_labels': consistency_labels,
        'consistency_data': consistency_data,
        'progress_labels': progress_labels,
        'progress_data': progress_data,
        'progress_value': progress_value,
    })


def profile_view(request):
    user_id = request.session.get('uid')
    if not user_id:
        return redirect('login')

    try:
        user_data = db.child("users").child(user_id).get().val()
        name = user_data.get("name", "Usuario")
        email = user_data.get("email", "correo@dominio.com")
        photo_url = user_data.get("profile_picture", "/static/main/user.png")
    except Exception as e:
        print("Error al obtener datos del perfil:", e)
        name = "Usuario"
        email = "correo@dominio.com"
        photo_url = "/static/main/user.png"

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
        storage.child(file_path).put(temp_path)
        # Obtén la URL de descarga
        photo_url = storage.child(file_path).get_url(None)
        # Borra el archivo temporal
        default_storage.delete(temp_path)
        # Actualiza la URL en la base de datos
        db.child("users").child(user_id).update({"profile_picture": photo_url})

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
            auth.update_user(
                user_id,
                display_name=display_name,
                photo_url=photo_url
            )
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

def get_profile(request, user_id):
    try:
        user = auth.get_user(user_id)
        return JsonResponse({
            'email': user.email,
            'display_name': user.display_name,
            'photo_url': user.photo_url
            
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


