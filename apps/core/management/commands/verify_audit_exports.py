import hashlib

from django.core.management.base import BaseCommand

from apps.core.models import AuditLogExport


class Command(BaseCommand):
    help = "Verify AuditLogExport file SHA256 and checksum chain linkage."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5000, help="Max exports to verify (latest first).")

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 5000)
        exports = list(AuditLogExport.objects.order_by("-id")[:limit])
        if not exports:
            self.stdout.write("No audit exports found.")
            return

        # Verify in chronological order to validate prev_sha256 chain.
        exports = list(reversed(exports))

        ok = 0
        failures = 0
        last_sha = ""

        for exp in exports:
            expected_prev = (exp.prev_sha256 or "").strip()
            if expected_prev and expected_prev != last_sha:
                failures += 1
                self.stderr.write(f"[FAIL] export_id={exp.id} prev_sha256 mismatch expected={expected_prev} actual={last_sha}")
                last_sha = exp.sha256
                continue

            try:
                data = exp.file.read()
                exp.file.seek(0)
            except Exception as exc:
                failures += 1
                self.stderr.write(f"[FAIL] export_id={exp.id} cannot read file: {exc}")
                last_sha = exp.sha256
                continue

            actual = hashlib.sha256(data).hexdigest()
            if actual != exp.sha256:
                failures += 1
                self.stderr.write(f"[FAIL] export_id={exp.id} sha256 mismatch expected={exp.sha256} actual={actual}")
            else:
                ok += 1

            last_sha = exp.sha256

        self.stdout.write(f"Verified exports: ok={ok} failed={failures} total={len(exports)}")
        if failures:
            raise SystemExit(1)

