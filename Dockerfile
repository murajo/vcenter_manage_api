FROM python:3.12

# Replace these with your own vCenter details
# These are placeholders and should be overwritten in your environment setup
ENV VCENTER_HOST='<your-vcenter-domain>'
ENV VCENTER_USER='<your-vcenter-user>'
ENV VCENTER_PASSWORD='<your-vcenter-password>'
# Set to 'True' if using a valid SSL certificate
ENV VERIFY_SSL='False' 

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "./src/app.py"]