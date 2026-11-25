from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('artistapp', '0002_alter_cart_options'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS tab_cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id VARCHAR(255) NOT NULL,
                    product_id INTEGER NOT NULL,
                    size_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    creation_dt DATETIME NOT NULL
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS tab_cart;",
        ),
    ]
