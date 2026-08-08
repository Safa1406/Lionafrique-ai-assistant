import subprocess
import sys

TESTS = [
    "test_lettre_ouverte_projet.py",
    "test_synopsis_nouvelle.py",
    "test_exemple_autobiographie.py",
    "test_cv_lettre_motivation.py",
]

failed = []

for test in TESTS:
    print("\n" + "#" * 110)
    print("RUNNING:", test)
    print("#" * 110)
    result = subprocess.run([sys.executable, test])
    if result.returncode != 0:
        failed.append(test)

print("\n" + "=" * 110)
print("BATCH 13-16 TERMINÉ")
print("=" * 110)

if failed:
    print("Scripts avec erreur d'exécution:")
    for test in failed:
        print("-", test)
    raise SystemExit(1)

print("Les 4 scripts se sont exécutés. Vérifiez les scores 30/30 de chaque rapport.")
