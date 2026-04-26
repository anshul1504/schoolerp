from django.shortcuts import render


def register_placeholder(request):
    return render(request, "accounts/register_placeholder.html")

