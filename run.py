from backend.app import app

# Module-level app for Vercel
__all__ = ['app']

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port, use_reloader=False)
