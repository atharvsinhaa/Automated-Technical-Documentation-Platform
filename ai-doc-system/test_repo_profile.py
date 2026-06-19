from backend.repository_intelligence.repository_profiler import RepositoryProfiler

profiler = RepositoryProfiler()

profile = profiler.profile("./")

print("\n===== REPOSITORY PROFILE =====\n")

print("Repository Type:", profile.repository_type)

print("\nLanguages:")
print(profile.languages)

print("\nFrameworks:")

for fw in profile.frameworks:
    print("-", fw.name)

print("\nDetected Modules:")

for module in profile.detected_modules:
    print("-", module)

print("\nEntrypoints:")

for ep in profile.entrypoints:
    print("-", ep.file_path)