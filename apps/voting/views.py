
# apps/voting/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator

# Voting views are implemented in core/views.py
# This file exists for app organization and future expansion