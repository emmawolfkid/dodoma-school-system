import logging
from io import BytesIO

from django.conf import settings

logger = logging.getLogger(__name__)

_signer_cache = None
_signer_load_attempted = False


def _load_signer():
    global _signer_cache, _signer_load_attempted
    if _signer_load_attempted:
        return _signer_cache
    _signer_load_attempted = True

    key_path = settings.BASE_DIR / 'signing' / 'school_signing.key.pem'
    cert_path = settings.BASE_DIR / 'signing' / 'school_signing.cert.pem'

    if not (key_path.exists() and cert_path.exists()):
        logger.info(
            "No signing certificate found at %s -- run "
            "'manage.py generate_signing_cert' to enable PDF signing. "
            "Documents will be issued unsigned until then.",
            key_path.parent,
        )
        return None

    try:
        from pyhanko.sign import signers
        _signer_cache = signers.SimpleSigner.load(
            key_file=str(key_path), cert_file=str(cert_path),
        )
    except Exception:
        logger.exception("Failed to load PDF signing certificate")
        _signer_cache = None

    return _signer_cache


def sign_pdf_bytes(pdf_bytes, reason='Official school document', location='Dodoma, Tanzania', field_name='DodomaSchoolSignature'):
    """
    Digitally signs a PDF (as bytes) with the school's signing certificate,
    if one has been generated (see generate_signing_cert management
    command). Returns the original bytes unsigned if no certificate is
    configured or signing fails for any reason -- signing is a
    nice-to-have integrity/provenance feature, not something that should
    ever block a document from being issued to a graduate.
    """
    signer = _load_signer()
    if signer is None:
        return pdf_bytes

    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign.signers import sign_pdf, PdfSignatureMetadata
        from pyhanko.sign.fields import SigFieldSpec

        writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
        signed = sign_pdf(
            writer,
            PdfSignatureMetadata(field_name=field_name, reason=reason, location=location),
            signer=signer,
            new_field_spec=SigFieldSpec(sig_field_name=field_name),
        )
        return signed.getvalue()
    except Exception:
        logger.exception("PDF signing failed -- issuing document unsigned")
        return pdf_bytes
