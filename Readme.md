# Basecamp Inspirational Quote Poster

This Streamlit application automates posting daily inspirational quotes with images to a Basecamp project message board, tagging project members by their first names (e.g., `@John`).

## Prerequisites
- **Python**: Version 3.12.2
- **Font File**: `Roboto-Bold.ttf` (optional; place in the project directory for better image rendering)
- **Basecamp Account**: Ensure you have access to a Basecamp project with a message board.
- **Pexels API Key**: Required for image fetching.

## Setup Instructions
1. **Clone or Extract the Files**
   - Ensure you have `app.py`, `requirements.txt`, `.env`, and optionally `Roboto-Bold.ttf`.

2. **Set Up the Environment**
   - Install Python 3.12.2 if not already installed.
   - Create a virtual environment (optional but recommended):
     ```bash
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate