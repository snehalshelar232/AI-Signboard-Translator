import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_sample_signboards():
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    font_path = "C:/Windows/Fonts/Nirmala.ttc"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/arial.ttf"

    # Font sizes
    title_font = ImageFont.truetype(font_path, 32, index=0)
    sub_font = ImageFont.truetype(font_path, 22, index=0)

    # 1. Tamil Signboard (Green Indian Highway Board)
    img_ta = Image.new("RGB", (640, 240), color=(18, 92, 45))
    draw_ta = ImageDraw.Draw(img_ta)
    draw_ta.rectangle([(10, 10), (630, 230)], outline=(255, 255, 255), width=4)
    draw_ta.text((40, 35), "சென்னை சென்ட்ரல்", font=title_font, fill=(255, 255, 255))
    draw_ta.text((40, 105), "வேகம் குறைக்கவும் - 40 கி.மீ/மணி", font=sub_font, fill=(255, 240, 100))
    draw_ta.text((40, 155), "வழி: மேடை 1 (PLATFORM 1)", font=sub_font, fill=(255, 255, 255))
    img_ta.save(out_dir / "sample_tamil_signboard.png")

    # 2. Marathi Signboard (Green Maharashtra Highway & School Zone)
    img_mr = Image.new("RGB", (640, 240), color=(18, 92, 45))
    draw_mr = ImageDraw.Draw(img_mr)
    draw_mr.rectangle([(10, 10), (630, 230)], outline=(255, 255, 255), width=4)
    draw_mr.text((40, 35), "पुणे - मुंबई द्रुतगती मार्ग", font=title_font, fill=(255, 255, 255))
    draw_mr.text((40, 105), "कृपया सावकाश चालवा - पुढे शाळा आहे", font=sub_font, fill=(255, 240, 100))
    draw_mr.text((40, 155), "वेगमर्यादा ५० किमी/तास (SPEED LIMIT 50)", font=sub_font, fill=(255, 255, 255))
    img_mr.save(out_dir / "sample_marathi_signboard.png")

    # 3. Gujarati Signboard (Blue Gujarat State Highway)
    img_gu = Image.new("RGB", (640, 240), color=(14, 60, 130))
    draw_gu = ImageDraw.Draw(img_gu)
    draw_gu.rectangle([(10, 10), (630, 230)], outline=(255, 255, 255), width=4)
    draw_gu.text((40, 35), "અમદાવાદ - ગાંધીનગર હાઇવે", font=title_font, fill=(255, 255, 255))
    draw_gu.text((40, 105), "ધીમે ચલાવો - આગળ વળાંક છે", font=sub_font, fill=(255, 230, 90))
    draw_gu.text((40, 155), "ગતિ મર્યાદા ૪૦ કિમી/કલાક (SPEED LIMIT 40)", font=sub_font, fill=(255, 255, 255))
    img_gu.save(out_dir / "sample_gujarati_signboard.png")

    # 4. Hindi Signboard (Blue Municipal Signboard)
    img_hi = Image.new("RGB", (640, 220), color=(14, 60, 130))
    draw_hi = ImageDraw.Draw(img_hi)
    draw_hi.rectangle([(10, 10), (630, 210)], outline=(255, 255, 255), width=4)
    draw_hi.text((40, 35), "कृपया धीरे चलें", font=title_font, fill=(255, 255, 255))
    draw_hi.text((40, 100), "आगे अस्पताल है - शांति बनाए रखें", font=sub_font, fill=(255, 230, 90))
    draw_hi.text((40, 150), "HOSPITAL ZONE - NO HONKING", font=sub_font, fill=(255, 255, 255))
    img_hi.save(out_dir / "sample_hindi_signboard.png")

    # 5. English Signboard (Yellow Caution Board)
    img_en = Image.new("RGB", (600, 200), color=(240, 185, 20))
    draw_en = ImageDraw.Draw(img_en)
    draw_en.rectangle([(10, 10), (590, 190)], outline=(20, 20, 20), width=5)
    draw_en.text((40, 35), "CAUTION: ONE WAY TRAFFIC", font=title_font, fill=(20, 20, 20))
    draw_en.text((40, 100), "DO NOT ENTER - SPEED LIMIT 30", font=sub_font, fill=(180, 20, 20))
    img_en.save(out_dir / "sample_english_signboard.png")

    # 6. Low Quality / Blurry Signboard (For testing unreadable/clarity warnings)
    img_blur = img_en.copy().filter(ImageFilter.GaussianBlur(radius=8))
    import numpy as np
    arr = np.array(img_blur) // 4
    Image.fromarray(arr).save(out_dir / "sample_blurry_signboard.png")

    print(f"Generated 6 authentic sample signboard images in: {out_dir}")

if __name__ == "__main__":
    create_sample_signboards()
