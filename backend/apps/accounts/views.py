from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "register"


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_scope = "login"


class LogoutView(APIView):
    """Revoke a refresh token so a stolen/leaked token stops working server-side."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "refresh token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            return Response({"detail": "invalid or expired refresh token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
