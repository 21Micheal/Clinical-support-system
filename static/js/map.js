document.addEventListener('DOMContentLoaded', () => {
  try {
    const diseaseData = JSON.parse(document.getElementById('disease-data').textContent);
    const genderStats = JSON.parse(document.getElementById('gender-stats').textContent);
    const ageGroupStats = JSON.parse(document.getElementById('age-group-stats').textContent);

    // Store global data at top level for accessibility
    const globalGenderLabels = genderStats.map(stat => stat.gender);
    const globalGenderData = genderStats.map(stat => stat.cases);
    const globalAgeGroupLabels = ageGroupStats.map(stat => stat.age_group);
    const globalAgeGroupData = ageGroupStats.map(stat => stat.cases);

    console.log("📊 Global Gender Data:", { labels: globalGenderLabels, data: globalGenderData });
    console.log("📊 Global Age Group Data:", { labels: globalAgeGroupLabels, data: globalAgeGroupData });

    const genderChartCanvas = document.getElementById('genderChart');
    const ageGroupChartCanvas = document.getElementById('ageGroupChart');

    let genderChartInstance = null;
    let ageGroupChartInstance = null;

    function renderGenderChart(data, labels) {
      console.log("🎨 Rendering Gender Chart:", { data, labels });
      
      // Validate data before rendering
      if (!data || !labels || data.length === 0 || labels.length === 0) {
        console.warn("⚠️ No gender data to display");
        return;
      }

      // Destroy existing chart if it exists
      if (genderChartInstance) {
        genderChartInstance.destroy();
        genderChartInstance = null;
      }

      if (genderChartCanvas) {
        const ctx = genderChartCanvas.getContext('2d');
        genderChartInstance = new Chart(ctx, {
          type: 'pie',
          data: {
            labels: labels,
            datasets: [{
              label: 'Gender Distribution',
              data: data,
              backgroundColor: ['#007bff', '#dc3545', '#ffc107'],
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
              legend: {
                display: true,
                position: 'bottom'
              },
              title: {
                display: true,
                text: 'Gender Distribution'
              }
            }
          }
        });
        console.log("✅ Gender chart rendered successfully");
      }
    }

    function renderAgeGroupChart(data, labels) {
      console.log("🎨 Rendering Age Group Chart:", { data, labels });
      
      // Validate data before rendering
      if (!data || !labels || data.length === 0 || labels.length === 0) {
        console.warn("⚠️ No age group data to display");
        return;
      }

      // Destroy existing chart if it exists
      if (ageGroupChartInstance) {
        ageGroupChartInstance.destroy();
        ageGroupChartInstance = null;
      }

      if (ageGroupChartCanvas) {
        const ctx = ageGroupChartCanvas.getContext('2d');
        ageGroupChartInstance = new Chart(ctx, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: 'Age Group Distribution',
              data: data,
              backgroundColor: ['#6c757d', '#28a745', '#17a2b8', '#ffc107'],
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: { 
              y: { 
                beginAtZero: true,
                ticks: {
                  stepSize: 1
                }
              } 
            },
            plugins: {
              legend: {
                display: false
              },
              title: {
                display: true,
                text: 'Age Group Distribution'
              }
            }
          },
        });
        console.log("✅ Age group chart rendered successfully");
      }
    }

    // Initial global render
    console.log("🚀 Initial chart render with global data");
    renderGenderChart(globalGenderData, globalGenderLabels);
    renderAgeGroupChart(globalAgeGroupData, globalAgeGroupLabels);

    // Map Setup
    const map = L.map('map').setView([-1.286389, 36.817223], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    // Add heatmap if available
    const heatPoints = Object.values(diseaseData).map(d => d.coordinates.concat(Math.sqrt(d.cases)));
    if (heatPoints.length > 0 && window.L && window.L.heatLayer) {
      L.heatLayer(heatPoints, { radius: 25 }).addTo(map);
    }

    const regionSelect = document.getElementById('region-filter');
    const sidebar = document.getElementById('region-sidebar');
    const regionList = [];

    // Process each region
    for (const region in diseaseData) {
      const regionData = diseaseData[region];
      if (!regionData || !regionData.coordinates || isNaN(regionData.cases)) {
        console.warn(`⚠️ Skipping region "${region}" due to invalid data.`);
        continue;
      }

      const { cases, coordinates, gender_stats = [], age_group_stats = [], diseases = [] } = regionData;

      console.log(`📍 Processing region: ${region}`, { 
        cases, 
        genderStatsCount: gender_stats.length, 
        ageStatsCount: age_group_stats.length 
      });

      // Fill select dropdown
      if (regionSelect) {
        const option = document.createElement('option');
        option.value = region;
        option.textContent = region;
        regionSelect.appendChild(option);
      }

      regionList.push({ region, cases });

      // Build gender and age group stats display
      const genderDisplay = gender_stats.length > 0 
        ? gender_stats.map(g => `<li>${g.gender}: ${g.cases} case${g.cases !== 1 ? 's' : ''}</li>`).join('') 
        : '<li class="text-muted">No data available</li>';
      
      const ageGroupDisplay = age_group_stats.length > 0 
        ? age_group_stats.map(a => `<li>${a.age_group}: ${a.cases} case${a.cases !== 1 ? 's' : ''}</li>`).join('') 
        : '<li class="text-muted">No data available</li>';

      const popupContent = `
        <div style="max-width:280px;">
          <h5 style="color:#007bff;">${region}</h5>
          <p><strong>Total Cases:</strong> ${cases}</p>
          <hr>
          <p><strong>Gender Distribution:</strong></p>
          <ul style="margin-bottom: 10px;">${genderDisplay}</ul>
          <p><strong>Age Groups:</strong></p>
          <ul style="margin-bottom: 10px;">${ageGroupDisplay}</ul>
          ${diseases.length > 0 ? `<button class="btn btn-sm btn-outline-primary mt-2" onclick="showDiseaseModal('${region}')">📋 View Disease Breakdown</button>` : ''}
        </div>
      `;

      const marker = L.circleMarker(coordinates, {
        radius: Math.sqrt(cases) * 2,
        color: cases > 15 ? 'red' : '#007bff',
        fillOpacity: 0.6,
      }).addTo(map).bindPopup(popupContent);

      // Handle marker click
      marker.on('click', () => {
        console.log(`🖱️ Clicked on region: ${region}`);
        map.setView(coordinates, 10);
        
        // Update charts with location-specific data OR fall back to global data
        if (gender_stats && gender_stats.length > 0) {
          const genderCases = gender_stats.map(g => g.cases);
          const genderLabels = gender_stats.map(g => g.gender);
          console.log(`📊 Using location-specific gender data for ${region}`);
          renderGenderChart(genderCases, genderLabels);
        } else {
          console.log(`📊 No location-specific gender data for ${region}, using global data`);
          renderGenderChart(globalGenderData, globalGenderLabels);
        }
        
        if (age_group_stats && age_group_stats.length > 0) {
          const ageCases = age_group_stats.map(a => a.cases);
          const ageLabels = age_group_stats.map(a => a.age_group);
          console.log(`📊 Using location-specific age data for ${region}`);
          renderAgeGroupChart(ageCases, ageLabels);
        } else {
          console.log(`📊 No location-specific age data for ${region}, using global data`);
          renderAgeGroupChart(globalAgeGroupData, globalAgeGroupLabels);
        }
      });
    }

    // Disease Modal Function
    window.showDiseaseModal = function(regionName) {
      const regionData = diseaseData[regionName];
      const diseases = regionData.diseases || [];

      const modalTitle = document.getElementById("modal-region-name");
      const diseaseListContainer = document.getElementById("disease-breakdown-list");

      modalTitle.textContent = regionName;
      diseaseListContainer.innerHTML = diseases.length > 0
        ? diseases.map(d => `<li class="list-group-item"><strong>${d.name}</strong>: ${d.cases} case${d.cases !== 1 ? 's' : ''}</li>`).join('')
        : `<li class="list-group-item">No disease data available.</li>`;

      const modal = new bootstrap.Modal(document.getElementById("diseaseModal"));
      modal.show();
    };

    // Populate sidebar
    if (sidebar) {
      regionList.sort((a, b) => b.cases - a.cases);
      sidebar.innerHTML = regionList.map(r => `<li>${r.region}: ${r.cases} case${r.cases !== 1 ? 's' : ''}</li>`).join('');
    }

    // Region dropdown change handler
    if (regionSelect) {
      regionSelect.addEventListener('change', () => {
        const selectedRegion = regionSelect.value;
        const selected = diseaseData[selectedRegion];
        
        console.log(`🔽 Dropdown selected: ${selectedRegion}`);
        
        if (selected && selected.coordinates) {
          map.setView(selected.coordinates, 10);
          
          // Update charts when region selected from dropdown
          const { gender_stats = [], age_group_stats = [] } = selected;
          
          if (gender_stats.length > 0) {
            console.log(`📊 Using dropdown gender data for ${selectedRegion}`);
            renderGenderChart(gender_stats.map(g => g.cases), gender_stats.map(g => g.gender));
          } else {
            console.log(`📊 No dropdown gender data for ${selectedRegion}, using global data`);
            renderGenderChart(globalGenderData, globalGenderLabels);
          }
          
          if (age_group_stats.length > 0) {
            console.log(`📊 Using dropdown age data for ${selectedRegion}`);
            renderAgeGroupChart(age_group_stats.map(a => a.cases), age_group_stats.map(a => a.age_group));
          } else {
            console.log(`📊 No dropdown age data for ${selectedRegion}, using global data`);
            renderAgeGroupChart(globalAgeGroupData, globalAgeGroupLabels);
          }
        }
      });
    }

    // Geolocation
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(pos => {
        const userMarker = L.marker([pos.coords.latitude, pos.coords.longitude]).addTo(map);
        userMarker.bindPopup("📍 You are here").openPopup();
      }, (error) => {
        console.warn("⚠️ Geolocation error:", error.message);
      });
    }

    // CSV Export
    const exportBtn = document.getElementById('export-data');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        const rows = [];

        // Collect all unique categories
        const genderSet = new Set();
        const ageGroupSet = new Set();
        const diseaseSet = new Set();

        for (const region in diseaseData) {
          const { gender_stats = [], age_group_stats = [], diseases = [] } = diseaseData[region];
          gender_stats.forEach(g => genderSet.add(g.gender));
          age_group_stats.forEach(a => ageGroupSet.add(a.age_group));
          diseases.forEach(d => diseaseSet.add(d.name));
        }

        const diseaseHeaders = [...diseaseSet].sort();
        const genderHeaders = [...genderSet].sort();
        const ageGroupHeaders = [...ageGroupSet].sort();

        const header = [
          "Region", 
          "Cases", 
          ...genderHeaders.map(g => `Gender: ${g}`), 
          ...ageGroupHeaders.map(a => `Age Group: ${a}`), 
          ...diseaseHeaders.map(d => `Disease: ${d}`)
        ];
        rows.push(header);

        // Data rows
        for (const region in diseaseData) {
          const data = diseaseData[region];
          const genderCounts = {};
          const ageGroupCounts = {};
          const diseaseCounts = {};

          (data.gender_stats || []).forEach(g => genderCounts[g.gender] = g.cases);
          (data.age_group_stats || []).forEach(a => ageGroupCounts[a.age_group] = a.cases);
          (data.diseases || []).forEach(d => diseaseCounts[d.name] = d.cases);

          const genderData = genderHeaders.map(g => genderCounts[g] || 0);
          const ageGroupData = ageGroupHeaders.map(a => ageGroupCounts[a] || 0);
          const diseaseDataValues = diseaseHeaders.map(d => diseaseCounts[d] || 0);

          rows.push([region, data.cases, ...genderData, ...ageGroupData, ...diseaseDataValues]);
        }

        const csvContent = rows.map(e => e.join(",")).join("\n");
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", "disease_data_detailed.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log("✅ CSV exported successfully");
      });
    } else {
      console.warn("⚠️ Export button with id 'export-data' not found.");
    }

  } catch (error) {
    console.error("❌ Initialization Error:", error);
  }
});



//document.addEventListener('DOMContentLoaded', () => {
//  try {
//    // Fetch JSON data
//    const diseaseData = JSON.parse(document.getElementById('disease-data').textContent);
//    const genderStats = JSON.parse(document.getElementById('gender-stats').textContent);
//    const ageGroupStats = JSON.parse(document.getElementById('age-group-stats').textContent);
//
//    // Debugging gender stats data
//    console.log("Gender Stats Debug:", genderStats);
//
//    // Check for missing or incorrect cases
//    const invalidGenderCases = genderStats.filter(stat => isNaN(stat.cases) || stat.cases < 0);
//    if (invalidGenderCases.length > 0) {
//      console.warn("Found invalid gender case data:", invalidGenderCases);
//    }
//
//    const genderLabels = genderStats.map(stat => stat.gender);
//    const genderData = genderStats.map(stat => stat.cases);
//    const ageGroupLabels = ageGroupStats.map(stat => stat.age_group);
//    const ageGroupData = ageGroupStats.map(stat => stat.cases);
//
//    // Render charts
//    const genderChartCanvas = document.getElementById('genderChart');
//    const ageGroupChartCanvas = document.getElementById('ageGroupChart');
//
//    if (genderChartCanvas) {
//      const genderChartCtx = genderChartCanvas.getContext('2d');
//      new Chart(genderChartCtx, {
//        type: 'pie',
//        data: {
//          labels: genderLabels,
//          datasets: [{
//            label: 'Gender Distribution',
//            data: genderData,
//            backgroundColor: ['#007bff', '#dc3545', '#ffc107'],
//          }],
//        },
//      });
//    }
//
//    if (ageGroupChartCanvas) {
//      const ageGroupChartCtx = ageGroupChartCanvas.getContext('2d');
//      new Chart(ageGroupChartCtx, {
//        type: 'bar',
//        data: {
//          labels: ageGroupLabels,
//          datasets: [{
//            label: 'Age Group Distribution',
//            data: ageGroupData,
//            backgroundColor: ['#6c757d', '#28a745', '#17a2b8', '#ffc107'],
//          }],
//        },
//        options: {
//          responsive: true,
//          scales: {
//            y: {
//              beginAtZero: true,
//            },
//          },
//        },
//      });
//    }
//
//    // Initialize map
//    const map = L.map('map').setView([-1.286389, 36.817223], 6);
//    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
//      attribution: '&copy; OpenStreetMap contributors',
//    }).addTo(map);
//
//    for (const region in diseaseData) {
//      const { cases, coordinates } = diseaseData[region];
//      L.circleMarker(coordinates, {
//        radius: Math.sqrt(cases) * 2,
//        color: cases > 15 ? 'red' : 'green',
//        fillOpacity: 0.5,
//      })
//        .addTo(map)
//        .bindPopup(`<strong>${region}</strong><br>Cases: ${cases}`);
//    }
//
//  } catch (error) {
//    console.error("Initialization Error:", error);
//  }
//});
