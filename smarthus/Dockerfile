ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY www /www
# Versjonsmerke fra innholdet, så telefoner og nettlesere alltid henter siste utgave
RUN sha1sum /www/smarthus-card.js | cut -c1-12 > /www/version.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
