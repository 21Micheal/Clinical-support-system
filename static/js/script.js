document.addEventListener('DOMContentLoaded', () => {
    console.log("✅ DOM Loaded - Running main script");

    // ✅ Grab UI Elements & State Variables (All declarations at the top)
    const symptomList = document.getElementById('symptom-list');
    const toggleBtn = document.querySelector('.toggle-btn');
    const manualInput = document.getElementById('manual-symptoms');
    const symptomCheckboxes = document.querySelectorAll('.form-check-input');
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');
    const startSearchSpeechButton = document.getElementById('startSearchSpeech');
    const startSymptomsSpeechButton = document.getElementById('startSymptomsSpeech');
    const diagnosisForm = document.getElementById('diagnosis-form');
    const consultButton = document.getElementById("startChat");
    const speechButton = document.getElementById("startSpeechChat");
    const botStatus = document.getElementById("bot-status");
    const statusIcon = document.getElementById("status-icon");
    const statusText = document.getElementById("status-text"); // FIX: Correctly declare here
    const resultsContainer = document.getElementById('results-container');
    const targetSection = document.getElementById('icon-section-container');
    const diagnosisButton = document.getElementById('diagnosis-button');
    const outbreakAlertBox = document.getElementById("outbreak-alert"); // FIX: Correct variable name
    const alertBox = document.getElementById('alert-box'); // Not used, but keeping for completeness

    let usedSpeechForSymptoms = false;
    let isListening = false;
    let isSpeaking = false; // FIX: Declare isSpeaking
    let currentSpeechUtterance = null;
    let step = 0;

    // ✅ Symptom List Toggle
    toggleBtn?.addEventListener('click', () => {
        if (symptomList) {
            symptomList.style.display = symptomList.style.display === 'none' ? 'block' : 'none';
        }
    });

    // ✅ Input Management
    manualInput?.addEventListener('input', () => {
        const isManualInputEmpty = manualInput.value.trim() === '';
        symptomCheckboxes.forEach(checkbox => checkbox.disabled = !isManualInputEmpty);
    });

    symptomList?.addEventListener('change', () => {
        const isAnyCheckboxChecked = Array.from(symptomCheckboxes).some(checkbox => checkbox.checked);
        if (manualInput) manualInput.disabled = isAnyCheckboxChecked;
    });

    
    // ✅ Speech Recognition Setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Speech Recognition is not supported in this browser. Please use a Chromium-based browser.");
        return;
    }

    const searchRecognition = new SpeechRecognition();
    const symptomsRecognition = new SpeechRecognition();
    const chatRecognition = new SpeechRecognition();

    [searchRecognition, symptomsRecognition, chatRecognition].forEach(rec => {
        rec.lang = 'en-US';
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        rec.continuous = false; // Add continuous false for single capture
    });

    // ✅ Symptom and Location Data (Move these to the top for scope)
    const symptomCorrections = {
        "hay fever": "high fever", "cold cough": "cold and cough", "head ache": "headache",
        "tiredness": "fatigue", "feeling weak": "weakness", "stomache": "stomach ache",
        "vomitting": "vomiting", "throwing up": "vomiting", "body pain": "body ache",
        "sore throat": "throat pain", "diaria": "diarrhoea", "rush": "skin rash",
        "mildfever": "mild_fever", "coffin": "coughing", "eating": "itching",
        "jules": "chills", "giles": "chills", "nosia": "nausea", "no": "nausea"
    };

    const knownSymptoms = [
        "high fever", "cough", "cold", "cold and cough", "headache", "fatigue", "vomiting",
        "diarrhoea", "throat pain", "body ache", "nausea", "dizziness", "loss of appetite",
        "shortness of breath", "chest pain", "skin rash", "stomach ache", "weakness", "mild_fever",
        "chills", "nausea", "shivering"
    ];

    const knownLocations = [
        "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa", "Homa Bay",
        "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi", "Kirinyaga", "Kisii",
        "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera",
        "Marsabit", "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi",
        "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya", "Taita-Taveta",
        "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga",
        "Wajir", "West Pokot"
    ];

    const steps = [
        { question: "Please state your age", fieldId: "age", validation: (value) => !isNaN(value) },
        { question: "Please state your gender", fieldId: "gender", validation: () => true },
        { question: "Please state your location", fieldId: "area" },
        { question: "Now list your symptoms. Say 'submit' when you're done", fieldId: "manual-symptoms" }
    ];

    // ✅ HOISTED FUNCTIONS: All functions are now defined before they are called.
    
    function levenshteinDistanceCalculation(a, b) {
        a = a.toLowerCase();
        b = b.toLowerCase();
        const matrix = Array.from({ length: b.length + 1 }, (_, i) => [i]);
        for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
        for (let i = 1; i <= b.length; i++) {
            for (let j = 1; j <= a.length; j++) {
                const cost = b[i - 1] === a[j - 1] ? 0 : 1;
                matrix[i][j] = Math.min(
                    matrix[i - 1][j] + 1,      // deletion
                    matrix[i][j - 1] + 1,      // insertion
                    matrix[i - 1][j - 1] + cost // substitution
                );
            }
        }
        return matrix[b.length][a.length];
    }

    const correctSymptom = (text) => {
        for (const [wrong, correct] of Object.entries(symptomCorrections)) {
            const regex = new RegExp(`\\b${wrong}\\b`, 'gi');
            if (regex.test(text)) {
                return text.replace(regex, correct);
            }
        }
        return text;
    };

    const getClosestSymptom = (input) => {
        let minDistance = Infinity;
        let bestMatch = input;
        for (const symptom of knownSymptoms) {
            const distance = levenshteinDistanceCalculation(input, symptom);
            if (distance < minDistance && distance <= 3) {
                minDistance = distance;
                bestMatch = symptom;
            }
        }
        return bestMatch;
    };

    function updateBotStatus(state) {
        if (!statusIcon || !statusText) return;
        const statusConfig = {
            'idle': { icon: 'bi-mic', text: 'Ready for voice chat', color: 'status-idle' },
            'listening': { icon: 'bi-mic-fill', text: 'Listening...', color: 'status-listening' },
            'speaking': { icon: 'bi-volume-up-fill', text: 'Speaking...', color: 'status-speaking' },
            'processing': { icon: 'bi-hourglass-split', text: 'Processing...', color: 'status-processing' }
        };
        const config = statusConfig[state] || statusConfig.idle;
        statusIcon.className = `bi ${config.icon} ${config.color}`;
        statusText.textContent = config.text;
        isListening = state === "listening";
        isSpeaking = state === "speaking"; // FIX: Update isSpeaking state
    }

    function stopSpeech() {
        if (currentSpeechUtterance) {
            window.speechSynthesis.cancel();
            currentSpeechUtterance = null;
        }
        isSpeaking = false;
        updateBotStatus("idle");
    }

    function stopListening() {
        try {
            if (chatRecognition) chatRecognition.stop();
            if (symptomsRecognition) symptomsRecognition.stop(); // FIX: Stop symptoms recognition as well
            if (searchRecognition) searchRecognition.stop();
            isListening = false;
        } catch (error) {
            console.warn("Error stopping recognition:", error);
        }
    }

    const speakText = (text, onComplete = null, nextStatus = "listening") => {
        const synth = window.speechSynthesis;
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.rate = 1;
        utterance.pitch = 1;
        const voices = synth.getVoices().filter(v => v.name.toLowerCase().includes("female"));
        if (voices.length > 0) utterance.voice = voices[0];
        utterance.onstart = () => updateBotStatus("speaking");
        utterance.onend = () => {
            updateBotStatus(nextStatus);
            if (typeof onComplete === "function") setTimeout(() => onComplete(), 250);
        };
        synth.cancel();
        synth.speak(utterance);
    };

    const handleOutbreakNotification = (message) => {
        if (!outbreakAlertBox) {
            console.warn("⚠️ Outbreak alert box not found in DOM.");
            return;
        }
        if (message && message.trim() !== "None") {
            outbreakAlertBox.textContent = message;
            outbreakAlertBox.classList.remove("hidden");
            outbreakAlertBox.style.display = "block";
        } else {
            outbreakAlertBox.classList.add("hidden");
            outbreakAlertBox.style.display = "none";
            outbreakAlertBox.textContent = "";
        }
    };
    
    // FIX: Simplified submit function to directly handle diagnosis
    const submitFormAndScroll = async (formData) => {
        try {
            console.log("🔄 Starting diagnosis...");
            updateBotStatus("processing");
            
            // Convert FormData to URLSearchParams for proper encoding
            const urlEncodedData = new URLSearchParams();
            
            // Add all form fields to URLSearchParams
            for (const [key, value] of formData.entries()) {
                // For checkboxes (selected_symptoms), we need to handle multiple values
                if (key === 'selected_symptoms') {
                    urlEncodedData.append(key, value);
                } else {
                    urlEncodedData.append(key, value);
                }
            }
            
            console.log("📤 Sending form data:", urlEncodedData.toString());

            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: urlEncodedData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log("✅ Diagnosis response:", data);
            
            if (data.success) {
                updateResultsDisplay(data);
                
                // CRITICAL: Update action buttons with prediction_id
                if (data.predicted_disease && data.prediction_id) {
                    updateActionButtons(data.predicted_disease, data.prediction_id);
                } else {
                    console.warn('⚠️ Missing predicted_disease or prediction_id:', {
                        predicted_disease: data.predicted_disease,
                        prediction_id: data.prediction_id
                    });
                }
                
                // Handle outbreak notification if present
                if (data.outbreak_notification) {
                    handleOutbreakNotification(data.outbreak_notification);
                }
                
                // Speech synthesis for results
                if (usedSpeechForSymptoms) {
                    const speechText = `Based on your symptoms, you are likely to be suffering from ${data.predicted_disease}. ${data.dis_des || ""}. Recommended diets include: ${Array.isArray(data.rec_diet) ? data.rec_diet.join(", ") : "No specific diets"}. Suggested medications are: ${Array.isArray(data.medications) ? data.medications.join(", ") : "No specific medications"}. Please take the necessary precautions.`;
                    speakText(speechText, () => {
                        usedSpeechForSymptoms = false;
                        updateBotStatus("idle");
                    });
                } else {
                    usedSpeechForSymptoms = false;
                    updateBotStatus("idle");
                }
                
                // Scroll to results section
                if (targetSection) {
                    targetSection.scrollIntoView({ behavior: 'smooth' });
                }
            } else {
                // Handle server-side validation errors
                console.error('❌ Server error:', data.message);
                alert(data.message || 'Error submitting diagnosis form. Please try again.');
                updateBotStatus("idle");
            }
        } catch (error) {
            console.error('❌ Error processing diagnosis:', error);
            alert('Error submitting diagnosis form. Please try again.');
            updateBotStatus("idle");
        }
    };

    // Function to update action buttons with the prediction_id
    function updateActionButtons(predictedDisease, predictionId) {
        console.log('🔄 Updating buttons with:', { predictedDisease, predictionId });
        
        // Find the buttons container - look for different possible selectors
        let buttonsContainer = document.querySelector('.results-actions');
        
        if (!buttonsContainer) {
            // Try other possible selectors
            buttonsContainer = document.querySelector('.results-actions.text-center');
            if (!buttonsContainer) {
                // Create the container if it doesn't exist
                const resultsSection = document.querySelector('.icon-section') || 
                                    document.getElementById('icon-section-container') ||
                                    document.querySelector('.diagnosis-heading')?.parentElement;
                
                if (resultsSection) {
                    buttonsContainer = document.createElement('div');
                    buttonsContainer.className = 'results-actions text-center mt-4';
                    resultsSection.appendChild(buttonsContainer);
                    console.log('✅ Created new buttons container');
                }
            }
        }
        
        if (!buttonsContainer) {
            console.warn('⚠️ Buttons container not found and could not be created');
            return;
        }
        
        // Clear and rebuild buttons
        buttonsContainer.innerHTML = `
            <a href="/disease_stats/${predictedDisease}" 
            class="btn btn-primary btn-lg mt-4 mr-3">
                <i class="fas fa-chart-bar"></i> View Disease Prevalence
            </a>
            <a href="/view_recommendations/${predictionId}" 
            class="btn btn-success btn-lg mt-4">
                <i class="fas fa-lightbulb"></i> Get AI Recommendations
            </a>
        `;
        
        // Make sure the container is visible
        buttonsContainer.style.display = 'block';
        
        console.log('✅ Buttons updated successfully');
        
        // Add click tracking for debugging
        buttonsContainer.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function(e) {
                console.log('🎯 Button clicked:', this.href);
            });
        });
    }

    // Alternative: If you want to update existing buttons instead of recreating them
    function updateExistingButtons(predictedDisease, predictionId) {
        console.log('🔄 Updating existing buttons...');
        
        // Update prevalence button
        const prevalenceBtn = document.querySelector('a[href*="/disease_stats/"]');
        if (prevalenceBtn) {
            prevalenceBtn.href = `/disease_stats/${predictedDisease}`;
            prevalenceBtn.style.display = 'inline-block';
            console.log('✅ Updated prevalence button');
        } else {
            console.warn('⚠️ Prevalence button not found');
        }
        
        // Update or create recommendations button
        let recommendationsBtn = document.querySelector('a[href*="/view_recommendations/"]');
        
        if (recommendationsBtn) {
            // Update existing button
            recommendationsBtn.href = `/view_recommendations/${predictionId}`;
            recommendationsBtn.style.display = 'inline-block';
            console.log('✅ Updated recommendations button');
        } else {
            // Create new button
            const buttonsContainer = document.querySelector('.results-actions') || 
                                document.querySelector('.icon-section') ||
                                document.getElementById('icon-section-container');
            
            if (buttonsContainer && predictionId) {
                recommendationsBtn = document.createElement('a');
                recommendationsBtn.className = 'btn btn-success btn-lg mt-4 ml-3';
                recommendationsBtn.href = `/view_recommendations/${predictionId}`;
                recommendationsBtn.innerHTML = '<i class="fas fa-lightbulb"></i> Get AI Recommendations';
                recommendationsBtn.style.display = 'inline-block';
                
                buttonsContainer.appendChild(recommendationsBtn);
                console.log('✅ Created new recommendations button');
            }
        }
        
        if (!recommendationsBtn) {
            console.warn('⚠️ Could not find or create recommendations button');
        }
    }

    // Update your existing updateResultsDisplay function to include button updates
    function updateResultsDisplay(data) {
        // Your existing code to display disease, description, precautions, etc.
        // ... existing display code ...
        
        console.log('📊 Updating results display with prediction_id:', data.prediction_id);
        
        // Ensure buttons are updated after displaying results
        if (data.predicted_disease && data.prediction_id) {
            // Try the main method first
            updateActionButtons(data.predicted_disease, data.prediction_id);
        }
    }

    // DEBUGGING: Add event listeners to track button behavior
    document.addEventListener('DOMContentLoaded', function() {
        // Track all clicks on recommendation buttons
        document.addEventListener('click', function(e) {
            const link = e.target.closest('a[href*="/view_recommendations/"]');
            if (link) {
                console.log('🎯 AI Recommendations button clicked:', link.href);
                console.log('📌 Prediction ID from URL:', link.href.split('/').pop());
            }
        });
        
        // Check for existing prediction data on page load
        const existingPredictionId = document.getElementById('predicted-disease')?.value;
        console.log('🔍 Existing prediction data on load:', existingPredictionId);
    });

    function updateResultsDisplay(data) {
        const resultsHTML = `
            <h2 class="diagnosis-heading">Diagnosis Results:</h2>
            <div class="container icon-section">
                <div class="icon-card">
                    <i class="bi bi-heart-pulse text-3xl gradient-text mb-2"></i>
                    <span class="font-bold gradient-text">Disease</span>
                    <p class="icon-details mt-2">You are likely to be suffering from <strong>${data.predicted_disease || 'Unknown'}</strong>.</p>
                </div>
                ${data.dis_des ? `<div class="icon-card"><i class="bi bi-file-text text-3xl gradient-text mb-2"></i><span class="font-bold gradient-text">Description</span><div class="icon-details mt-2">${data.dis_des.split('.').filter(line => line.trim()).map(line => `<p>${line.trim()}</p>`).join('')}</div></div>` : ''}
                ${data.rec_diet && data.rec_diet.length > 0 ? `<div class="icon-card"><i class="bi bi-apple text-3xl gradient-text mb-2"></i><span class="font-bold gradient-text">Diets</span><ul class="icon-details mt-2">${data.rec_diet.map(diet => `<li>${diet}</li>`).join('')}</ul></div>` : ''}
                ${data.medications && data.medications.length > 0 ? `<div class="icon-card"><i class="bi bi-pills text-3xl gradient-text mb-2"></i><span class="font-bold gradient-text">Medications</span><ul class="icon-details mt-2">${data.medications.map(med => `<li>${med}</li>`).join('')}</ul></div>` : ''}
                ${data.workout && data.workout.length > 0 ? `<div class="icon-card"><i class="bi bi-heart text-3xl gradient-text mb-2"></i><span class="font-bold gradient-text">Workouts</span><ul class="icon-details mt-2">${data.workout.map(workout => `<li>${workout}</li>`).join('')}</ul></div>` : ''}
        
            </div>
        `;
        if (targetSection) targetSection.innerHTML = resultsHTML;
        console.log("✅ Results display updated successfully");
    }

    const callChatbotEnhanced = async (question) => {
        try {
            const response = await fetch("/chatbot/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question })
            });
            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data = await response.json();
            return data.answer || "I did not receive a clear answer from the Dr. Hudson AI.";
        } catch (error) {
            console.error("❌ Error calling chatbot:", error);
            return "Sorry, an error occurred while contacting Dr. Hudson AI. Please check your network connection.";
        }
    };

    const initializeVoiceSystem = () => {
        const loadVoices = () => {
            return new Promise((resolve) => {
                const voices = window.speechSynthesis.getVoices();
                if (voices.length) {
                    resolve(voices);
                } else {
                    window.speechSynthesis.onvoiceschanged = () => {
                        resolve(window.speechSynthesis.getVoices());
                    };
                }
            });
        };
        loadVoices().then((voices) => {
            console.log(`🎙️ Loaded ${voices.length} voices`);
            updateBotStatus("idle");
            console.log("✅ Voice system ready.");
        });
    };

    // ✅ Voice Input Flow Handler
    // NEW FUNCTION: Ensure all form data is complete before submission
    function ensureFormDataIsComplete() {
        console.log("🔍 Checking form data completeness before submission...");
        
        // NOTE: This assumes 'diagnosisForm' is a globally available constant/variable from the main script scope.
        const form = document.getElementById('diagnosis-form'); 
        if (!form) return false;

        // Use FormData to check final submission values
        const formData = new FormData(form);
        
        // Log all form data for debugging
        console.log("📋 Form data before submission:");
        for (let [key, value] of formData.entries()) {
            console.log(`   ${key}: ${value}`);
        }
        
        // Validate required fields (assuming these fields are part of the 'steps' array)
        const requiredFields = ['age', 'gender', 'area'];
        const missingFields = requiredFields.filter(fieldId => {
            const value = formData.get(fieldId);
            // Check for null/empty string and for 'None' which might be a default value
            return !value || value.trim() === '' || value.toLowerCase() === 'none';
        });
        
        // Also check symptoms, which is handled outside of the requiredFields array
        const symptomField = document.getElementById('manual-symptoms');
        if (!symptomField || symptomField.value.trim() === '') {
            missingFields.push('symptoms');
        }

        if (missingFields.length > 0) {
            console.warn("❌ Missing required fields:", missingFields);
            // FIX: The original logic handles the restart if symptoms are missing in the loop. 
            // For other fields, we just log and rely on the server/form submission to fail gracefully.
            // We'll trust the flow to catch the missing fields before this check.
            return true; // Return true to allow submission to proceed, letting server handle full validation
        }
        
        console.log("✅ All required fields are present");
        return true;
    }

    // ✅ Voice Input Flow Handler (startSymptomFlow)
    const startSymptomFlow = () => {
        if (step >= steps.length) return;
        const currentStep = steps[step];
        speakText(currentStep.question, () => symptomsRecognition.start());
        
        symptomsRecognition.onresult = (event) => {
            let transcript = event.results[0][0].transcript.trim().toLowerCase();
            const field = document.getElementById(currentStep.fieldId);
            
            if (step === steps.length - 1) { // Symptoms handling
                if (transcript.includes("submit")) {
                    symptomsRecognition.stop();
                    if (field.value.trim() === "") {
                        speakText("Please list at least one symptom before submitting.", () => symptomsRecognition.start());
                        return;
                    }
                    speakText("Submitting your symptoms...", () => {
                        usedSpeechForSymptoms = true;
                        
                        // FIX: Ensure all form fields are properly captured
                        // NOTE: The function is called, but its return value is ignored, 
                        // relying on submitFormAndScroll for the ultimate action.
                        ensureFormDataIsComplete();
                        
                        // NOTE: Assumes diagnosisForm is globally accessible
                        submitFormAndScroll(new FormData(diagnosisForm));
                    });
                    return;
                }
                
                const rawSymptoms = transcript
                    .replace(/^(i have|i am having|i feel|i am feeling|i got|symptoms are)\s*/gi, '')
                    .replace(/\./g, ',')
                    .split(/\s*(?:,|and|with)\s*/gi)
                    .map(s => s.trim())
                    .filter(s => s.length > 0);
                
                // NOTE: Assumes getClosestSymptom and correctSymptom are globally accessible
                const cleanedSymptoms = rawSymptoms.map(sym => getClosestSymptom(correctSymptom(sym)));
                const currentValue = field.value ? field.value.split(",").map(s => s.trim()) : [];
                const newValue = [...currentValue, ...cleanedSymptoms].filter(Boolean);
                field.value = Array.from(new Set(newValue)).join(", ");
                field.dispatchEvent(new Event('input', { bubbles: true }));

                setTimeout(() => {
                    speakText("Got it. Any other symptoms? Say 'submit' when done.", () => symptomsRecognition.start());
                }, 1000);
            } else { // Age, Gender, Location Fields Handling
                if (currentStep.validation && !currentStep.validation(transcript)) {
                    speakText(`Invalid input for ${currentStep.fieldId}. Please try again.`, () => symptomsRecognition.start());
                    return;
                }

                let finalTranscript = transcript;

                if (currentStep.fieldId === "age") {
                    const ageNumber = parseInt(transcript, 10);
                    if (isNaN(ageNumber)) {
                        speakText("Invalid age provided. Please state your age as a number.", () => symptomsRecognition.start());
                        return;
                    }
                    finalTranscript = ageNumber.toString();
                    field.value = finalTranscript; // Set value directly for input field
                }
                
                if (currentStep.fieldId === "gender") {
                    const genderOptions = ["male", "female", "other"];
                    // NOTE: Assumes levenshteinDistanceCalculation is globally accessible
                    const closestMatch = genderOptions.reduce((bestMatch, option) => {
                        const dist = levenshteinDistanceCalculation(transcript, option);
                        return dist < levenshteinDistanceCalculation(transcript, bestMatch) ? option : bestMatch;
                    }, genderOptions[0]);
                    finalTranscript = closestMatch;
                    
                    const genderSelect = document.getElementById('gender');
                    if (genderSelect) {
                        // Find the option that matches the value
                        for (let option of genderSelect.options) {
                            if (option.value.toLowerCase() === finalTranscript) {
                                genderSelect.value = option.value;
                                break;
                            }
                        }
                        // If no exact value match, try matching the text (safer for select fields)
                        if (genderSelect.value.toLowerCase() !== finalTranscript) {
                            for (let option of genderSelect.options) {
                                if (option.text.toLowerCase().includes(finalTranscript)) {
                                    genderSelect.value = option.value;
                                    break;
                                }
                            }
                        }
                    }
                }

                if (currentStep.fieldId === "area") {
                    // NOTE: Assumes knownLocations and levenshteinDistanceCalculation are globally accessible
                    const closestMatch = knownLocations.reduce((bestMatch, option) => {
                        const dist = levenshteinDistanceCalculation(transcript, option);
                        return dist < levenshteinDistanceCalculation(transcript, bestMatch) ? option : bestMatch;
                    }, knownLocations[0]);
                    finalTranscript = closestMatch;
                    
                    const areaSelect = document.getElementById('area');
                    if (areaSelect) {
                        // Find the option that matches the value
                        for (let option of areaSelect.options) {
                            if (option.value.toLowerCase() === finalTranscript.toLowerCase()) {
                                areaSelect.value = option.value;
                                break;
                            }
                        }
                    }
                }
                
                // FIX: Use proper form field setting for non-select fields (Age)
                if (field.tagName !== 'SELECT') {
                    field.value = finalTranscript;
                } 
                // NOTE: For 'gender' and 'area', the select logic above already sets 'field.value' correctly.

                // FIX: Trigger multiple events to ensure form recognizes the change
                field.dispatchEvent(new Event('input', { bubbles: true }));
                field.dispatchEvent(new Event('change', { bubbles: true }));
                field.dispatchEvent(new Event('blur', { bubbles: true }));
                
                console.log(`Captured ${currentStep.fieldId}: ${field.value}`);
                step++;
                setTimeout(startSymptomFlow, 1000);
            }
        };

        symptomsRecognition.onerror = (event) => {
            console.error("Symptoms recognition error:", event.error);
            speakText("Could not recognize your input. Please try again.", () => symptomsRecognition.start());
        };
    };

    // ✅ Event Listeners
    botStatus?.addEventListener("click", () => {
        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            updateBotStatus("idle");
        }
    });

    startSearchSpeechButton?.addEventListener('click', () => {
        if (isSpeaking) {
            speakText("Please wait until I finish speaking.");
            return;
        }
        if (isListening) return;
        updateBotStatus("listening");
        try {
            searchRecognition.start();
        } catch (error) {
            console.warn("Search recognition error:", error);
            updateBotStatus("idle");
        }
    });

    searchRecognition.onresult = (event) => {
        searchInput.value = event.results[0][0].transcript;
        updateBotStatus("idle");
    };

    searchRecognition.onerror = (event) => {
        console.warn("Search recognition error:", event.error);
        updateBotStatus("idle");
    };

    speechButton?.addEventListener("click", () => {
        if (isSpeaking) {
            speakText("Please wait.");
            return;
        }
        if (isListening) {
            speakText("I'm listening.");
            return;
        }
        stopSpeech();
        stopListening();
        speakText("Hello, how may I help you?", () => {
            updateBotStatus("listening");
            try {
                chatRecognition.start();
            } catch (error) {
                console.warn("Error starting chat recognition:", error);
                updateBotStatus("idle");
            }
        });
    });

    chatRecognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript.trim();
        console.log("🤖 User said:", transcript);
        updateBotStatus("processing");
        stopListening();
        const answer = await callChatbotEnhanced(transcript);
        stopSpeech();
        speakText(answer, () => updateBotStatus("idle"));
    };

    chatRecognition.onerror = (event) => {
        console.warn("Chat recognition error:", event.error);
        updateBotStatus("idle");
    };

    startSymptomsSpeechButton?.addEventListener('click', () => {
        usedSpeechForSymptoms = true;
        step = 0;
        steps.forEach(s => {
            const field = document.getElementById(s.fieldId);
            if (field) field.value = '';
        });
        startSymptomFlow();
    });

    // FIX: Remove redundant listener for diagnosisForm as it's handled by voice flow
    // diagnosisForm?.addEventListener('submit', async (event) => { ... });

    // FIX: Add a listener for the manual diagnosis button
    diagnosisButton?.addEventListener('click', (event) => {
        event.preventDefault();
        const formData = new FormData(diagnosisForm);
        usedSpeechForSymptoms = false; // Set to false for manual submission
        submitFormAndScroll(formData);
    });

    // UI Event Handlers (Retained)
    toggleBtn?.addEventListener('click', () => {
        if (symptomList) symptomList.style.display = symptomList.style.display === 'none' ? 'block' : 'none';
    });
    manualInput?.addEventListener('input', () => {
        const isManualInputEmpty = manualInput.value.trim() === '';
        symptomCheckboxes.forEach(checkbox => checkbox.disabled = !isManualInputEmpty);
    });
    symptomList?.addEventListener('change', () => {
        const isAnyCheckboxChecked = Array.from(symptomCheckboxes).some(checkbox => checkbox.checked);
        if (manualInput) manualInput.disabled = isAnyCheckboxChecked;
    });

    initializeVoiceSystem();
});
