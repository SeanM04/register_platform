from django.db import migrations


def seed_admin_user_type(apps, schema_editor):
    UserType = apps.get_model("accounts", "UserType")
    UserType.objects.get_or_create(code="admin", defaults={"name": "Admin"})


def unseed_admin_user_type(apps, schema_editor):
    UserType = apps.get_model("accounts", "UserType")
    UserType.objects.filter(code="admin").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_admin_user_type, unseed_admin_user_type),
    ]
