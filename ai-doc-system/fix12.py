import re
import shutil

# Restore clean originals to avoid compound patch errors
shutil.copyfile("extractor_original.py", "backend/object_model_extractor/extractor.py")
shutil.copyfile("lld_generator_original.py", "backend/document_generator/lld_generator.py")

print("Files restored. Ready to patch.")
