FROM davisking/dlib:latest  # Maintained by dlib’s creator

WORKDIR /app
COPY . .
RUN pip install --upgrade pip
RUN pip install -r backend/requirements.txt
EXPOSE 5000
CMD ["gunicorn", "--chdir", "backend", "app:app", "--bind", "0.0.0.0:5000"]
