from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from docx import Document
from fpdf import FPDF
from PyPDF2 import PdfReader
import tempfile, os, textwrap

app = FastAPI()

# Allow frontend
origins = [
    "https://ai-cover-letter-flax.vercel.app",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- Helpers ---
def extract_text_from_pdf(path):
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(path):
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

# --- Generate Cover Letter ---
@app.post("/generate_cover_letter")
async def generate_cover_letter(
    resume: UploadFile,
    job_description: str = Form(""),
    word_count: int = Form(200)
):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{resume.filename}") as tmp:
            tmp.write(await resume.read())
            tmp_path = tmp.name

        resume_text = (
            extract_text_from_pdf(tmp_path)
            if resume.filename.lower().endswith(".pdf")
            else extract_text_from_docx(tmp_path)
        )

        prompt = f"""
        You are a professional career assistant.
        Write a plagiarism-free, formal cover letter based on the following resume and job description.

        - Keep it under {word_count} words.
        - Maintain a 3–4 paragraph format.
        - Focus on achievements and tone relevant to the role.

        Resume:
        {resume_text}

        Job Description:
        {job_description}
        """

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # fast and free model
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes professional cover letters."},
                {"role": "user", "content": prompt},
            ],
        )

        cover_letter = completion.choices[0].message.content.strip()
        return JSONResponse({"cover_letter": cover_letter})

    except Exception as e:
        print("[ERROR]", e)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# --- DOCX Download ---
@app.post("/download_docx")
async def download_docx(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(tmp.name)
    return FileResponse(tmp.name, filename="cover_letter.docx")

# --- PDF Download ---
@app.post("/download_pdf")
async def download_pdf(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_auto_page_break(auto=True, margin=15)

    for paragraph in text.split("\n"):
        if paragraph.strip():
            wrapped = textwrap.fill(paragraph, width=90)
            pdf.multi_cell(0, 10, wrapped)
        else:
            pdf.ln(5)

    pdf.output(tmp.name)
    return FileResponse(tmp.name, filename="cover_letter.pdf")

@app.get("/")
def root():
    return {"message": "✅ Groq-powered AI Cover Letter API running!"}
