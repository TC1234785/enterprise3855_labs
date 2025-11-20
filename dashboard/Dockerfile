FROM nginx:alpine

# Copy dashboard files to nginx html directory
COPY index.html /usr/share/nginx/html/
COPY updateStats.js /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
