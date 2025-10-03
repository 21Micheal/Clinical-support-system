 // Initialize the map and set view to Kenya
      const map = L.map('map').setView([-1.286389, 36.817223], 6);

      // Add OpenStreetMap tiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);

      // Disease data from Flask (Jinja2 template rendering)
      const diseaseData = {{ disease_data | tojson }};
      console.log(diseaseData);


      // Add markers for each region
      for (const region in diseaseData) {
        const { cases, coordinates } = diseaseData[region];
        L.marker(coordinates)
          .addTo(map)
          .bindPopup(`${region}: ${cases} cases`)
          .openPopup();
      }