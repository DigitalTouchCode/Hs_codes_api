from rest_framework import serializers
from .models import User, HsCode, Category, HsCodeFile


class HsCodeFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = HsCodeFile
        fields = ["hs_code_file"]


class HsCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HsCode
        fields = "__all__"


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name"]


class HsCodeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
