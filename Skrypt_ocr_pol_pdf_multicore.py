import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from PyPDF2 import PdfWriter
from PyPDF2 import PdfReader
from functools import partial

from pathlib import Path
from PIL import Image

class OCRProcessor:

    @staticmethod
    def __ocr_tiff_to_pdf(language, tmp_pdf_dir: Path, tiff_path: Path) -> Path:
        output_pdf_path = tmp_pdf_dir / (tiff_path.stem + ".pdf")
        try:
            subprocess.run([
                "tesseract",
                str(tiff_path),
                str(output_pdf_path.with_suffix("")),
                "-l", language , "pdf"
            ], check=True)
            print(f"Utworzono: {output_pdf_path.name}")
        except subprocess.CalledProcessError:
            print(f"Błąd OCR dla: {tiff_path.name}")
        return output_pdf_path

    def run(self, selected_directory: Path, language: str):
        # Ustawienia ścieżek
        pdf_dir = selected_directory / "pdf"
        tmp_pdf_dir = selected_directory / "tmp_pdf"
        bitmapa_dir = selected_directory / "bitmapa"
        cover_dir = selected_directory / "okladka"
        tmp_tiffs_dir = selected_directory / "tmp_tiffs"

        #Ustawienia
        language = "pol"

        # Tworzenie folderów
        print("Tworzenie folderów pdf, bitmapa oraz okladka...")
        for folder in [pdf_dir, bitmapa_dir, cover_dir, tmp_pdf_dir, tmp_tiffs_dir]:
            folder.mkdir(exist_ok=True)
        print("Foldery zostały stworzone")

        # Konwersja .tif do .jpg
        print("Tworzenie jpgów...")
        jpg_created = False
        for tif_path in selected_directory.glob("*.tif"):
            jpg_path = bitmapa_dir / (tif_path.stem + ".jpg")
            try:
                subprocess.run(["magick", str(tif_path), str(jpg_path)], check=True)
                if jpg_path.exists():
                    jpg_created = True
            except subprocess.CalledProcessError:
                print(f"Nie udało się przekonwertować: {tif_path.name}")

        if jpg_created:
            print("JPG pliki zostały stworzone pomyślnie w folderze 'bitmapa'")
        else:
            print("Żadne JPG pliki nie zostały stworzone.")

        # Stworzenie okładki (pierwszy plik jpg)
        print("Tworzenie okładki...")
        jpg_files = list(bitmapa_dir.glob("*.jpg"))
        if jpg_files:
            shutil.copy(jpg_files[0], cover_dir)
            print("Okładka została pomyślnie stworzona w folderze 'okladka'.")
        else:
            print("Wystąpił błąd i okładka nie została stworzona!")

        # Stworzenie PDF OCR
        print("Tworzenie skompresowanych kopii TIFFów...")
        tmp_tiffs_dir.mkdir(exist_ok=True)

        for tif_path in selected_directory.glob("*.tif"):
            out_path = tmp_tiffs_dir / tif_path.name
            try:
                subprocess.run([
                    "magick", str(tif_path),
                    "-resize", "80%",
                    "-compress", "JPEG",
                    "-quality", "60",
                    str(out_path)
                ], check=True)
            except subprocess.CalledProcessError:
                print(f"Błąd konwersji: {tif_path.name}")


        # Lista plików TIFF
        tiff_files = sorted(tmp_tiffs_dir.glob("*.tif"))

        # Wyjściowe PDF-y z OCR
        ocr_output_pdfs = []

        # Wykorzystanie połowy dostępnych logicznych rdzeni
        num_workers = max(1, (multiprocessing.cpu_count() * 0.75) - 1)

        print(f"Rozpoczynanie OCR na {len(tiff_files)} plikach TIFF z użyciem {num_workers} wątków...")

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            func = partial(OCRProcessor.__ocr_tiff_to_pdf, language, tmp_pdf_dir)
            ocr_output_pdfs = list(executor.map(func, tiff_files))

        # Filtrowanie tylko istniejących PDF-ów
        ocr_output_pdfs = [p for p in ocr_output_pdfs if p.exists()]

        # Łączenie PDF-ów
        merger = PdfWriter()

        for pdf in (sorted(tmp_pdf_dir.glob("*.pdf"))):
            merger.append(pdf)

        merger.write(pdf_dir / "merged.pdf")
        merger.close()

        #Wyciaganie txt z PDF-ów
        '''txt_extractor = PdfReader(pdf_dir / "merged.pdf")
        text = ""
        for page in txt_extractor.pages:
            text += page.extract_text()

        text_path = pdf_dir / "merged.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        '''
        # Sprzątanie
        shutil.rmtree(tmp_tiffs_dir, ignore_errors=True)
        shutil.rmtree(tmp_pdf_dir, ignore_errors=True)

        print("Proces zakończony.")


if __name__ == "__main__":
    selected_directory = Path.cwd()
    language = "pol+eng"
    ocr_processor = OCRProcessor()
    ocr_processor.run(selected_directory, language)
