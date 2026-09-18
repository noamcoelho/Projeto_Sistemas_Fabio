output "ip_publico" {
  value = aws_instance.sd.public_ip
}

output "servico" {
  value = "http://${aws_instance.sd.public_ip}:8080/"
}

output "ssh" {
  value = "ssh -i <chave.pem> ubuntu@${aws_instance.sd.public_ip}"
}

output "zona" {
  value = aws_instance.sd.availability_zone
}

output "grupo_seguranca" {
  value = aws_security_group.sd.id
}
