from rest_framework import serializers
from .models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password


class RegisterSerializer(serializers.ModelSerializer):
    # password = serializers.CharField(write_only=True, min_length=6)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ["email", "name", "password", "password2"]
        
    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data) 
        return user
    
# class LoginSerializer(serializers.ModelSerializer):
#     email = serializers.EmailField()

#     class Meta:
#         model = User
#         fields = ["email", "password"]

class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()