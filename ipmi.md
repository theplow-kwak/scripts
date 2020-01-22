# IPMI/BMC 관련 정보

16F KTNF 서버 정보

* IP: 10.92.170.71
* admin / skhynix!1



## IPMI 

ipmi tool 을 사용하여 remote server에 접근시 필요한 옵션: 

- -I intf        Interface to use
- -H hostname    Remote host name for LAN interface
- -U username    Remote session username
- -E             Read password from IPMI_PASSWORD environment variable
  * sudo 명령어 사용시 환경변수를 상속받기 위하여 sudo **-E** option 사용

```bash
export IPMI_PASSWORD='skhynix!1'
sudo -E ipmitool -I lanplus -H 10.92.170.71 -U admin -E chassis status
```



ipmitool 사용법 예제

https://help.univention.com/t/how-to-do-remote-server-administration-over-ipmi/6778



## redfish

### redfishtool



https://github.com/DMTF/Redfishtool



```bash
redfishtool -r 10.92.168.29 -u root -p $IPMI_PASSWORD
```







```
python -m SimpleHTTPServer 8000
python3 -m http.server 8000
```