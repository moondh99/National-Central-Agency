from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers='localhost:9092')
producer.send('test-topic', b'hello kafka from python')
producer.flush()
print("메시지 전송 완료")