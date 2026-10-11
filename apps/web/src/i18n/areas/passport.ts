import type { Area } from '../area'

/** The roll passport: where one roll came from, what was done to it, how it was checked and sent. */
export const passport = {
  'passport.printLabel': {
    en: 'Print label', hi: 'लेबल प्रिंट करें', kn: 'ಲೇಬಲ್ ಮುದ್ರಿಸಿ', ta: 'லேபிளை அச்சிடு', te: 'లేబుల్ ప్రింట్ చేయండి',
    mr: 'लेबल छापा', bn: 'লেবেল ছাপুন', gu: 'લેબલ પ્રિન્ટ કરો', ml: 'ലേബൽ പ്രിന്റ് ചെയ്യുക', pa: 'ਲੇਬਲ ਛਾਪੋ',
  },
  'passport.scanned': {
    en: 'Scanned roll {code}. Opening its passport.', hi: 'रोल {code} स्कैन हुआ। उसका पासपोर्ट खुल रहा है।', kn: 'ರೋಲ್ {code} ಸ್ಕ್ಯಾನ್ ಆಯಿತು. ಅದರ ಪಾಸ್‌ಪೋರ್ಟ್ ತೆರೆಯಲಾಗುತ್ತಿದೆ.', ta: 'ரோல் {code} ஸ்கேன் ஆனது. அதன் பாஸ்போர்ட் திறக்கிறது.', te: 'రోల్ {code} స్కాన్ అయింది. దాని పాస్‌పోర్ట్ తెరుస్తోంది.',
    mr: 'रोल {code} स्कॅन झाला. त्याचा पासपोर्ट उघडत आहे.', bn: 'রোল {code} স্ক্যান হয়েছে। এর পাসপোর্ট খুলছে।', gu: 'રોલ {code} સ્કેન થયો. તેનો પાસપોર્ટ ખૂલી રહ્યો છે.', ml: 'റോൾ {code} സ്കാൻ ചെയ്തു. അതിന്റെ പാസ്പോർട്ട് തുറക്കുന്നു.', pa: 'ਰੋਲ {code} ਸਕੈਨ ਹੋਇਆ। ਉਸਦਾ ਪਾਸਪੋਰਟ ਖੁੱਲ੍ਹ ਰਿਹਾ ਹੈ।',
  },
  'passport.orderFor': {
    en: 'for', hi: 'के लिए', kn: 'ಗಾಗಿ', ta: 'க்காக', te: 'కోసం',
    mr: 'साठी', bn: 'এর জন্য', gu: 'માટે', ml: 'നായി', pa: 'ਲਈ',
  },
  'passport.buyerDeadline': {
    en: 'Buyer deadline {date}', hi: 'खरीदार की अंतिम तारीख़ {date}', kn: 'ಖರೀದಿದಾರರ ಗಡುವು {date}', ta: 'வாங்குபவர் காலக்கெடு {date}', te: 'కొనుగోలుదారు గడువు {date}',
    mr: 'खरेदीदाराची मुदत {date}', bn: 'ক্রেতার সময়সীমা {date}', gu: 'ખરીદદારની સમયમર્યાદા {date}', ml: 'വാങ്ങുന്നയാളുടെ സമയപരിധി {date}', pa: 'ਖਰੀਦਦਾਰ ਦੀ ਆਖ਼ਰੀ ਤਾਰੀਖ਼ {date}',
  },
  'passport.yarn': {
    en: 'Yarn', hi: 'सूत', kn: 'ನೂಲು', ta: 'நூல்', te: 'నూలు',
    mr: 'सूत', bn: 'সুতো', gu: 'સૂતર', ml: 'നൂൽ', pa: 'ਸੂਤ',
  },
  'passport.recalled': {
    en: 'Recalled', hi: 'वापस मँगाया गया', kn: 'ಹಿಂಪಡೆಯಲಾಗಿದೆ', ta: 'திரும்பப் பெறப்பட்டது', te: 'వెనక్కి తీసుకున్నారు',
    mr: 'परत मागवले', bn: 'ফেরত নেওয়া হয়েছে', gu: 'પાછું મંગાવ્યું', ml: 'തിരിച്ചുവിളിച്ചു', pa: 'ਵਾਪਸ ਮੰਗਵਾਇਆ',
  },
  'passport.noYarn': {
    en: 'No yarn lot recorded yet.', hi: 'अभी कोई सूत लॉट दर्ज नहीं।', kn: 'ಇನ್ನೂ ನೂಲಿನ ಲಾಟ್ ದಾಖಲಾಗಿಲ್ಲ.', ta: 'இன்னும் நூல் லாட் பதிவாகவில்லை.', te: 'ఇంకా నూలు లాట్ నమోదు కాలేదు.',
    mr: 'अजून सुताचा लॉट नोंदवलेला नाही.', bn: 'এখনও কোনো সুতোর লট নথিভুক্ত হয়নি।', gu: 'હજુ સૂતરનો લોટ નોંધાયો નથી.', ml: 'ഇതുവരെ നൂൽ ലോട്ട് രേഖപ്പെടുത്തിയിട്ടില്ല.', pa: 'ਅਜੇ ਕੋਈ ਸੂਤ ਲਾਟ ਦਰਜ ਨਹੀਂ।',
  },
  'passport.machines': {
    en: 'Machines', hi: 'मशीनें', kn: 'ಯಂತ್ರಗಳು', ta: 'இயந்திரங்கள்', te: 'యంత్రాలు',
    mr: 'यंत्रे', bn: 'যন্ত্র', gu: 'મશીનો', ml: 'യന്ത്രങ്ങൾ', pa: 'ਮਸ਼ੀਨਾਂ',
  },
  'passport.stage.rework': {
    en: 'Rework', hi: 'दोबारा काम', kn: 'ಮರುಕೆಲಸ', ta: 'மறுபணி', te: 'రీవర్క్',
    mr: 'पुन्हा काम', bn: 'পুনরায় কাজ', gu: 'ફરી કામ', ml: 'വീണ്ടും പണി', pa: 'ਦੁਬਾਰਾ ਕੰਮ',
  },
  'passport.runLine': {
    en: '{stage} on {machine} · {operator}', hi: '{machine} पर {stage} · {operator}', kn: '{machine} ನಲ್ಲಿ {stage} · {operator}', ta: '{machine} இல் {stage} · {operator}', te: '{machine} పై {stage} · {operator}',
    mr: '{machine} वर {stage} · {operator}', bn: '{machine}-এ {stage} · {operator}', gu: '{machine} પર {stage} · {operator}', ml: '{machine}-ൽ {stage} · {operator}', pa: '{machine} ਤੇ {stage} · {operator}',
  },
  'passport.byHand': {
    en: 'manual mending', hi: 'हाथ से मरम्मत', kn: 'ಕೈಯಿಂದ ದುರಸ್ತಿ', ta: 'கைமுறை சரிசெய்தல்', te: 'చేతితో మరమ్మతు',
    mr: 'हाताने दुरुस्ती', bn: 'হাতে মেরামত', gu: 'હાથે સમારકામ', ml: 'കൈകൊണ്ട് നന്നാക്കൽ', pa: 'ਹੱਥ ਨਾਲ ਮੁਰੰਮਤ',
  },
  'passport.runRange': {
    en: '{from} to {to}', hi: '{from} से {to} तक', kn: '{from} ರಿಂದ {to} ವರೆಗೆ', ta: '{from} முதல் {to} வரை', te: '{from} నుండి {to} వరకు',
    mr: '{from} ते {to}', bn: '{from} থেকে {to}', gu: '{from} થી {to}', ml: '{from} മുതൽ {to} വരെ', pa: '{from} ਤੋਂ {to} ਤੱਕ',
  },
  'passport.stillRunning': {
    en: 'still running', hi: 'अभी चल रहा है', kn: 'ಇನ್ನೂ ಓಡುತ್ತಿದೆ', ta: 'இன்னும் இயங்குகிறது', te: 'ఇంకా నడుస్తోంది',
    mr: 'अजून चालू आहे', bn: 'এখনও চলছে', gu: 'હજુ ચાલુ છે', ml: 'ഇപ്പോഴും ഓടുന്നു', pa: 'ਅਜੇ ਚੱਲ ਰਿਹਾ ਹੈ',
  },
  'passport.qualityChecks': {
    en: 'Quality checks', hi: 'गुणवत्ता जाँच', kn: 'ಗುಣಮಟ್ಟ ಪರಿಶೀಲನೆಗಳು', ta: 'தரச் சோதனைகள்', te: 'నాణ్యత తనిఖీలు',
    mr: 'गुणवत्ता तपासण्या', bn: 'গুণমান পরীক্ষা', gu: 'ગુણવત્તા તપાસ', ml: 'ഗുണനിലവാര പരിശോധനകൾ', pa: 'ਗੁਣਵੱਤਾ ਜਾਂਚਾਂ',
  },
  'passport.notChecked': {
    en: 'This roll has not been checked yet.', hi: 'इस रोल की अभी जाँच नहीं हुई।', kn: 'ಈ ರೋಲ್ ಅನ್ನು ಇನ್ನೂ ಪರಿಶೀಲಿಸಿಲ್ಲ.', ta: 'இந்த ரோல் இன்னும் சோதிக்கப்படவில்லை.', te: 'ఈ రోల్‌ను ఇంకా తనిఖీ చేయలేదు.',
    mr: 'या रोलची अजून तपासणी झालेली नाही.', bn: 'এই রোল এখনও পরীক্ষা করা হয়নি।', gu: 'આ રોલ હજુ તપાસાયો નથી.', ml: 'ഈ റോൾ ഇതുവരെ പരിശോധിച്ചിട്ടില്ല.', pa: 'ਇਸ ਰੋਲ ਦੀ ਅਜੇ ਜਾਂਚ ਨਹੀਂ ਹੋਈ।',
  },
  'passport.overrodeAi': {
    en: 'The inspector overrode the AI suggestion.', hi: 'निरीक्षक ने एआई का सुझाव बदल दिया।', kn: 'ಇನ್‌ಸ್ಪೆಕ್ಟರ್ ಎಐ ಸಲಹೆಯನ್ನು ಬದಲಿಸಿದರು.', ta: 'ஆய்வாளர் ஏஐ பரிந்துரையை மாற்றினார்.', te: 'ఇన్‌స్పెక్టర్ ఏఐ సూచనను మార్చారు.',
    mr: 'निरीक्षकाने एआयची सूचना बदलली.', bn: 'পরিদর্শক এআই-এর পরামর্শ বদলেছেন।', gu: 'નિરીક્ષકે એઆઈનું સૂચન બદલ્યું.', ml: 'ഇൻസ്പെക്ടർ എഐ നിർദേശം മാറ്റി.', pa: 'ਨਿਰੀਖਕ ਨੇ ਏਆਈ ਦਾ ਸੁਝਾਅ ਬਦਲ ਦਿੱਤਾ।',
  },
  'passport.dispatch': {
    en: 'Dispatch', hi: 'रवानगी', kn: 'ರವಾನೆ', ta: 'அனுப்புதல்', te: 'డిస్పాచ్',
    mr: 'रवानगी', bn: 'প্রেরণ', gu: 'રવાનગી', ml: 'അയയ്ക്കൽ', pa: 'ਰਵਾਨਗੀ',
  },
  'passport.dispatchLoading': {
    en: ', loading', hi: ', लोड हो रहा है', kn: ', ಲೋಡ್ ಆಗುತ್ತಿದೆ', ta: ', ஏற்றப்படுகிறது', te: ', లోడ్ అవుతోంది',
    mr: ', लोड होत आहे', bn: ', লোড হচ্ছে', gu: ', લોડ થઈ રહ્યું છે', ml: ', ലോഡ് ചെയ്യുന്നു', pa: ', ਲੋਡ ਹੋ ਰਿਹਾ ਹੈ',
  },
  'passport.vehicle': {
    en: 'Vehicle {no}', hi: 'गाड़ी {no}', kn: 'ವಾಹನ {no}', ta: 'வாகனம் {no}', te: 'వాహనం {no}',
    mr: 'वाहन {no}', bn: 'গাড়ি {no}', gu: 'વાહન {no}', ml: 'വാഹനം {no}', pa: 'ਗੱਡੀ {no}',
  },
  'passport.invoice': {
    en: 'Invoice', hi: 'बिल', kn: 'ಇನ್‌ವಾಯ್ಸ್', ta: 'விலைப்பட்டியல்', te: 'ఇన్‌వాయిస్',
    mr: 'बिल', bn: 'চালান', gu: 'બિલ', ml: 'ഇൻവോയ്സ്', pa: 'ਬਿੱਲ',
  },
  'passport.notDispatched': {
    en: 'This roll has not been dispatched.', hi: 'इस रोल की रवानगी नहीं हुई।', kn: 'ಈ ರೋಲ್ ಅನ್ನು ಇನ್ನೂ ರವಾನಿಸಿಲ್ಲ.', ta: 'இந்த ரோல் இன்னும் அனுப்பப்படவில்லை.', te: 'ఈ రోల్ ఇంకా పంపబడలేదు.',
    mr: 'या रोलची रवानगी झालेली नाही.', bn: 'এই রোল এখনও পাঠানো হয়নি।', gu: 'આ રોલ હજુ મોકલાયો નથી.', ml: 'ഈ റോൾ ഇതുവരെ അയച്ചിട്ടില്ല.', pa: 'ਇਸ ਰੋਲ ਦੀ ਰਵਾਨਗੀ ਨਹੀਂ ਹੋਈ।',
  },
  'passport.cost': {
    en: 'True cost', hi: 'असली लागत', kn: 'ನಿಜವಾದ ವೆಚ್ಚ', ta: 'உண்மையான செலவு', te: 'అసలు ఖర్చు',
    mr: 'खरा खर्च', bn: 'প্রকৃত খরচ', gu: 'સાચો ખર્ચ', ml: 'യഥാർത്ഥ ചെലവ്', pa: 'ਅਸਲ ਖ਼ਰਚਾ',
  },
  'passport.costMissing': {
    en: 'Cost is not available yet.', hi: 'लागत अभी उपलब्ध नहीं है।', kn: 'ವೆಚ್ಚ ಇನ್ನೂ ಲಭ್ಯವಿಲ್ಲ.', ta: 'செலவு இன்னும் கிடைக்கவில்லை.', te: 'ఖర్చు ఇంకా అందుబాటులో లేదు.',
    mr: 'खर्च अजून उपलब्ध नाही.', bn: 'খরচ এখনও পাওয়া যায়নি।', gu: 'ખર્ચ હજુ ઉપલબ્ધ નથી.', ml: 'ചെലവ് ഇതുവരെ ലഭ്യമല്ല.', pa: 'ਖ਼ਰਚਾ ਅਜੇ ਉਪਲਬਧ ਨਹੀਂ।',
  },
  'passport.perMetre': {
    en: 'Cost per metre', hi: 'प्रति मीटर लागत', kn: 'ಪ್ರತಿ ಮೀಟರ್ ವೆಚ್ಚ', ta: 'மீட்டருக்கான செலவு', te: 'మీటరుకు ఖర్చు',
    mr: 'प्रति मीटर खर्च', bn: 'প্রতি মিটারের খরচ', gu: 'મીટર દીઠ ખર્ચ', ml: 'മീറ്ററിന് ചെലവ്', pa: 'ਪ੍ਰਤੀ ਮੀਟਰ ਖ਼ਰਚਾ',
  },
  'passport.provisionalHint': {
    en: 'Provisional: the order is not finished', hi: 'अनंतिम: ऑर्डर पूरा नहीं हुआ है', kn: 'ತಾತ್ಕಾಲಿಕ: ಆರ್ಡರ್ ಇನ್ನೂ ಮುಗಿದಿಲ್ಲ', ta: 'தற்காலிகம்: ஆர்டர் இன்னும் முடியவில்லை', te: 'తాత్కాలికం: ఆర్డర్ ఇంకా పూర్తి కాలేదు',
    mr: 'तात्पुरते: ऑर्डर पूर्ण झालेला नाही', bn: 'অস্থায়ী: অর্ডার এখনও শেষ হয়নি', gu: 'કામચલાઉ: ઓર્ડર હજુ પૂરો થયો નથી', ml: 'താൽക്കാലികം: ഓർഡർ പൂർത്തിയായിട്ടില്ല', pa: 'ਆਰਜ਼ੀ: ਆਰਡਰ ਅਜੇ ਪੂਰਾ ਨਹੀਂ ਹੋਇਆ',
  },
  'passport.final': {
    en: 'Final', hi: 'अंतिम', kn: 'ಅಂತಿಮ', ta: 'இறுதி', te: 'తుది',
    mr: 'अंतिम', bn: 'চূড়ান্ত', gu: 'અંતિમ', ml: 'അന്തിമം', pa: 'ਅੰਤਿਮ',
  },
  'passport.provisional': {
    en: 'Provisional', hi: 'अनंतिम', kn: 'ತಾತ್ಕಾಲಿಕ', ta: 'தற்காலிகம்', te: 'తాత్కాలికం',
    mr: 'तात्पुरते', bn: 'অস্থায়ী', gu: 'કામચલાઉ', ml: 'താൽക്കാലികം', pa: 'ਆਰਜ਼ੀ',
  },
  'passport.totalRoll': {
    en: 'Total for this roll', hi: 'इस रोल का कुल', kn: 'ಈ ರೋಲ್‌ನ ಒಟ್ಟು', ta: 'இந்த ரோலுக்கான மொத்தம்', te: 'ఈ రోల్ మొత్తం',
    mr: 'या रोलचा एकूण', bn: 'এই রোলের মোট', gu: 'આ રોલનો કુલ', ml: 'ഈ റോളിന്റെ ആകെ', pa: 'ਇਸ ਰੋਲ ਦਾ ਕੁੱਲ',
  },
  'passport.whereMoney': {
    en: 'Where the money went', hi: 'पैसा कहाँ गया', kn: 'ಹಣ ಎಲ್ಲಿ ಹೋಯಿತು', ta: 'பணம் எங்கே சென்றது', te: 'డబ్బు ఎక్కడికి వెళ్లింది',
    mr: 'पैसे कुठे गेले', bn: 'টাকা কোথায় গেছে', gu: 'પૈસા ક્યાં ગયા', ml: 'പണം എവിടെ പോയി', pa: 'ਪੈਸਾ ਕਿੱਥੇ ਗਿਆ',
  },
  'passport.amount': {
    en: 'Amount', hi: 'रकम', kn: 'ಮೊತ್ತ', ta: 'தொகை', te: 'మొత్తం',
    mr: 'रक्कम', bn: 'পরিমাণ', gu: 'રકમ', ml: 'തുക', pa: 'ਰਕਮ',
  },
  'passport.machinesCost': {
    en: 'Machines', hi: 'मशीनें', kn: 'ಯಂತ್ರಗಳು', ta: 'இயந்திரங்கள்', te: 'యంత్రాలు',
    mr: 'यंत्रे', bn: 'যন্ত্র', gu: 'મશીનો', ml: 'യന്ത്രങ്ങൾ', pa: 'ਮਸ਼ੀਨਾਂ',
  },
  'passport.labour': {
    en: 'Labour', hi: 'मज़दूरी', kn: 'ಕೂಲಿ', ta: 'தொழிலாளர் செலவு', te: 'కూలీ',
    mr: 'मजुरी', bn: 'মজুরি', gu: 'મજૂરી', ml: 'കൂലി', pa: 'ਮਜ਼ਦੂਰੀ',
  },
  'passport.rejectShare': {
    en: 'Share of rejected rolls', hi: 'नामंज़ूर रोलों का हिस्सा', kn: 'ತಿರಸ್ಕೃತ ರೋಲ್‌ಗಳ ಪಾಲು', ta: 'நிராகரிக்கப்பட்ட ரோல்களின் பங்கு', te: 'తిరస్కరించిన రోల్స్ వాటా',
    mr: 'नामंजूर रोलचा वाटा', bn: 'বাতিল রোলের অংশ', gu: 'નામંજૂર રોલનો હિસ્સો', ml: 'നിരസിച്ച റോളുകളുടെ പങ്ക്', pa: 'ਰੱਦ ਰੋਲਾਂ ਦਾ ਹਿੱਸਾ',
  },
  'passport.defect.hole.one': {
    en: '{count} hole', hi: '{count} छेद', kn: '{count} ರಂಧ್ರ', ta: '{count} துளை', te: '{count} రంధ్రం',
    mr: '{count} छिद्र', bn: '{count}টি ফুটো', gu: '{count} છિદ્ર', ml: '{count} ദ്വാരം', pa: '{count} ਛੇਕ',
  },
  'passport.defect.hole.many': {
    en: '{count} holes', hi: '{count} छेद', kn: '{count} ರಂಧ್ರಗಳು', ta: '{count} துளைகள்', te: '{count} రంధ్రాలు',
    mr: '{count} छिद्रे', bn: '{count}টি ফুটো', gu: '{count} છિદ્રો', ml: '{count} ദ്വാരങ്ങൾ', pa: '{count} ਛੇਕ',
  },
  'passport.defect.stain.one': {
    en: '{count} stain', hi: '{count} दाग', kn: '{count} ಕಲೆ', ta: '{count} கறை', te: '{count} మరక',
    mr: '{count} डाग', bn: '{count}টি দাগ', gu: '{count} ડાઘ', ml: '{count} കറ', pa: '{count} ਦਾਗ਼',
  },
  'passport.defect.stain.many': {
    en: '{count} stains', hi: '{count} दाग', kn: '{count} ಕಲೆಗಳು', ta: '{count} கறைகள்', te: '{count} మరకలు',
    mr: '{count} डाग', bn: '{count}টি দাগ', gu: '{count} ડાઘ', ml: '{count} കറകൾ', pa: '{count} ਦਾਗ਼',
  },
  'passport.defect.thread_fault.one': {
    en: '{count} thread fault', hi: '{count} धागे की खराबी', kn: '{count} ದಾರದ ದೋಷ', ta: '{count} நூல் குறைபாடு', te: '{count} దారం లోపం',
    mr: '{count} धाग्याचा दोष', bn: '{count}টি সুতোর ত্রুটি', gu: '{count} દોરાની ખામી', ml: '{count} നൂൽ തകരാർ', pa: '{count} ਧਾਗੇ ਦਾ ਨੁਕਸ',
  },
  'passport.defect.thread_fault.many': {
    en: '{count} thread faults', hi: '{count} धागे की खराबियाँ', kn: '{count} ದಾರದ ದೋಷಗಳು', ta: '{count} நூல் குறைபாடுகள்', te: '{count} దారం లోపాలు',
    mr: '{count} धाग्याचे दोष', bn: '{count}টি সুতোর ত্রুটি', gu: '{count} દોરાની ખામીઓ', ml: '{count} നൂൽ തകരാറുകൾ', pa: '{count} ਧਾਗੇ ਦੇ ਨੁਕਸ',
  },
  'passport.defect.colour_mismatch.one': {
    en: '{count} colour mismatch', hi: '{count} रंग में अंतर', kn: '{count} ಬಣ್ಣ ವ್ಯತ್ಯಾಸ', ta: '{count} நிற வேறுபாடு', te: '{count} రంగు తేడా',
    mr: '{count} रंगातील फरक', bn: '{count}টি রঙের অমিল', gu: '{count} રંગ તફાવત', ml: '{count} നിറ വ്യത്യാസം', pa: '{count} ਰੰਗ ਦਾ ਫ਼ਰਕ',
  },
  'passport.defect.colour_mismatch.many': {
    en: '{count} colour mismatches', hi: '{count} रंग में अंतर', kn: '{count} ಬಣ್ಣ ವ್ಯತ್ಯಾಸಗಳು', ta: '{count} நிற வேறுபாடுகள்', te: '{count} రంగు తేడాలు',
    mr: '{count} रंगातील फरक', bn: '{count}টি রঙের অমিল', gu: '{count} રંગ તફાવતો', ml: '{count} നിറ വ്യത്യാസങ്ങൾ', pa: '{count} ਰੰਗ ਦੇ ਫ਼ਰਕ',
  },
  'passport.defect.other.one': {
    en: '{count} other defect', hi: '{count} अन्य खराबी', kn: '{count} ಇತರ ದೋಷ', ta: '{count} பிற குறைபாடு', te: '{count} ఇతర లోపం',
    mr: '{count} इतर दोष', bn: '{count}টি অন্য ত্রুটি', gu: '{count} અન્ય ખામી', ml: '{count} മറ്റ് തകരാർ', pa: '{count} ਹੋਰ ਨੁਕਸ',
  },
  'passport.defect.other.many': {
    en: '{count} other defects', hi: '{count} अन्य खराबियाँ', kn: '{count} ಇತರ ದೋಷಗಳು', ta: '{count} பிற குறைபாடுகள்', te: '{count} ఇతర లోపాలు',
    mr: '{count} इतर दोष', bn: '{count}টি অন্য ত্রুটি', gu: '{count} અન્ય ખામીઓ', ml: '{count} മറ്റ് തകരാറുകൾ', pa: '{count} ਹੋਰ ਨੁਕਸ',
  },
} satisfies Area
