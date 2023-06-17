
NAME = Notification
XML_FILES = profile/*/*.xml 

# sudo apt-get install libxml2-utils libxml2-dev
check:
	echo ${XML_FILES}
	xmllint --noout ${XML_FILES}


zip:
	zip -x@zip_exclude.lst -r ${NAME}.zip *

zip_free:
	cat zip_exclude.lst zip_exclude_free.lst > zip_exclude_free_full.lst
	cp nodes/__init__.py .
	echo "from .UDMobile import UDMobile" > nodes/__init__.py
	echo "from .Controller import Controller" >> nodes/__init__.py
	zip -x@zip_exclude_free_full.lst -r ${NAME}_free.zip *
	mv __init__.py nodes/
