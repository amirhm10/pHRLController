FROM python:3.12.2

ADD run_opc_emulator.py .
ADD biosmb_opc_emulator.py .
ADD requirements.txt .

RUN pip install -r requirements.txt

CMD ["python", "./run_opc_emulator.py"]