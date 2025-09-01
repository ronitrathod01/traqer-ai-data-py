from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

from .serializer import RegisterSerializer, LoginSerializer, User

class RegisterView(APIView):
    
    def post(self, request):
        exitisting_user = User.objects.filter(email=request.data.get('email'))
        if exitisting_user.exists():
            return Response(
                {"message": "user with this email already exits"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"message": "User registered successfully", 
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                    "apiKey": user.api_key,
                    }},
            status=status.HTTP_201_CREATED,
        )
        
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.data.get("email")
        password = serializer.data.get("password")
        
        user = authenticate(request, email=email, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            
        refresh = RefreshToken.for_user(user)
        
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {"id": user.id, "email": user.email, "name": user.name},
            },
            status=status.HTTP_200_OK,
        )