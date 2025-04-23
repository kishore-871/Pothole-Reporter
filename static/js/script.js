let recognition;
    let userLocation = null;
    let locationApproved = null;
    let reportConfirmed = false;
    let lastBotMessage = "";
    let messageHistory = [];

    // Get GPS on load
    window.onload = () => {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            userLocation = {
              lat: position.coords.latitude,
              lon: position.coords.longitude
            };
            console.log("📍 Location:", userLocation);
          },
          (err) => {
            console.warn("GPS Error:", err.message);
          }
        );
      }

      // Enter to send typed message
      document.getElementById("text-input").addEventListener("keydown", function(e) {
        if (e.key === "Enter") {
          sendTypedMessage();
        }
      });
    };

    function speak(text) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-US';
      speechSynthesis.speak(utterance);
    }

    function startListening() {
      recognition = new(window.SpeechRecognition || window.webkitSpeechRecognition)();
      recognition.lang = 'en-US';
      recognition.start();

      recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        document.getElementById("spoken-text").innerText = "You said: " + transcript;
        handleChat(transcript);
      };
    }

    function sendTypedMessage() {
      const inputField = document.getElementById("text-input");
      const typedText = inputField.value.trim();
      if (typedText) {
        document.getElementById("spoken-text").innerText = "You typed: " + typedText;
        handleChat(typedText);
        inputField.value = "";
      }
    }

    async function handleChat(transcript) {
      let reviseSummary = false;

      // Check for GPS consent
      if (lastBotMessage.toLowerCase().includes("use your current location")) {
        const intentRes = await fetch("/check_intent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: transcript })
        });
        const intentData = await intentRes.json();
        locationApproved = intentData.agreed === true;
      }

      // Check for report confirmation or revision
      // if (
      //   /is this (correct|accurate|right)|does everything look good?/i.test(lastBotMessage)
      // ) {
      //   const intentRes = await fetch("/check_intent", {
      //     method: "POST",
      //     headers: { "Content-Type": "application/json" },
      //     body: JSON.stringify({ message: transcript })
      //   });
      //   const intentData = await intentRes.json();
      //   reportConfirmed = intentData.agreed === true;

      //   console.log("✅ Report confirmed:", reportConfirmed);

      //   if (!reportConfirmed && transcript.toLowerCase().match(/(not|no|wrong|change|fix|edit|revise)/)) {
      //     reviseSummary = true;
      //   }
      // }

      messageHistory.push({ role: "user", content: transcript });
      reportConfirmed = false;
      reviseSummary = false;

      const match = lastBotMessage.match(/{[\s\S]*?}/);
      let validSummaryExists = false;

      try {
        if (match) {
          const parsed = JSON.parse(match[0]);
          if (parsed.location && parsed.description) {
            validSummaryExists = true;
          }
        }
      } catch (e) {
        // JSON parse error ignored
      }

      if (validSummaryExists) {
        const intentRes = await fetch("/check_intent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: transcript })
        });
        const intentData = await intentRes.json();
        reportConfirmed = intentData.agreed === true;

        if (!reportConfirmed && /not|no|wrong|change|fix|edit|revise/i.test(transcript)) {
          reviseSummary = true;
        }
      }


      const payload = {
        message: transcript,
        location: locationApproved && userLocation ? userLocation : null,
        locationApproved: locationApproved,
        reportConfirmed: reportConfirmed,
        reviseSummary: reviseSummary,
        history: messageHistory
      };
      
      console.log("📤 Sending to /chat:", payload);

      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      const botText = data.reply || data.error;
      messageHistory.push({ role: "assistant", content: botText });
      lastBotMessage = botText;

      document.getElementById("bot-reply").innerText = "Bot: " + botText;
      speak(botText);
    }