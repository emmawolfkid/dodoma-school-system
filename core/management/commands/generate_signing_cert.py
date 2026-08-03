import datetime
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Generates a self-signed certificate + private key for digitally "
        "signing official PDFs (certificate collection receipts, etc). "
        "This is a SELF-signed cert: it proves the PDF wasn't altered "
        "after signing and records who/when it was signed, but it will "
        "show as 'untrusted' in Adobe Reader unless the school's cert is "
        "explicitly trusted by the reader, or replaced with one issued by "
        "a recognized CA. Re-running overwrites any existing cert/key."
    )

    def handle(self, *args, **options):
        signing_dir = settings.BASE_DIR / 'signing'
        os.makedirs(signing_dir, exist_ok=True)
        key_path = signing_dir / 'school_signing.key.pem'
        cert_path = signing_dir / 'school_signing.cert.pem'

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'TZ'),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Dodoma'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Dodoma Secondary School'),
            x509.NameAttribute(NameOID.COMMON_NAME, 'Dodoma Secondary School Document Signer'),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, content_commitment=True, key_encipherment=False,
                    data_encipherment=False, key_agreement=False, key_cert_sign=False,
                    crl_sign=False, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .sign(key, hashes.SHA256())
        )

        with open(key_path, 'wb') as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        with open(cert_path, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        self.stdout.write(self.style.SUCCESS(f"Signing key written to {key_path}"))
        self.stdout.write(self.style.SUCCESS(f"Signing certificate written to {cert_path}"))
        self.stdout.write(
            "Keep both files out of git (already covered by .gitignore) and "
            "back them up -- losing the key means re-signing everything with a new one."
        )
