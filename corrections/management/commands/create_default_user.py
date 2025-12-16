# corrections/management/commands/create_default_user.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Создает дефолтного пользователя для админки'

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                password='admin',
                email='admin@example.com'
            )
            self.stdout.write(self.style.SUCCESS('Создан пользователь admin:admin'))
        else:
            self.stdout.write(self.style.WARNING('⚠Пользователь admin уже существует'))
