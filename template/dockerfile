FROM us-docker.pkg.dev/colab-images/public/runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir eezyml

COPY . .

RUN eezy init

EXPOSE 5000

CMD ["eezy", "start"]
