import type { Area } from '../area'

/** Words every screen leans on: the mill's name, small labels, and the revenue-and-cost chart. */
export const common = {
  'brand.first': {
    en: 'Everest', hi: 'एवरेस्ट', kn: 'ಎವರೆಸ್ಟ್', ta: 'எவரெஸ்ட்', te: 'ఎవరెస్ట్',
    mr: 'एव्हरेस्ट', bn: 'এভারেস্ট', gu: 'એવરેસ્ટ', ml: 'എവറസ്റ്റ്', pa: 'ਐਵਰੈਸਟ',
  },
  'brand.rest': {
    en: 'Mills', hi: 'मिल्स', kn: 'ಮಿಲ್ಸ್', ta: 'மில்ஸ்', te: 'మిల్స్',
    mr: 'मिल्स', bn: 'মিলস', gu: 'મિલ્સ', ml: 'മിൽസ്', pa: 'ਮਿੱਲਜ਼',
  },
  'brand.name': {
    en: 'Everest Mills', hi: 'एवरेस्ट मिल्स', kn: 'ಎವರೆಸ್ಟ್ ಮಿಲ್ಸ್', ta: 'எவரெஸ்ட் மில்ஸ்', te: 'ఎవరెస్ట్ మిల్స్',
    mr: 'एव्हरेस्ट मिल्स', bn: 'এভারেস্ট মিলস', gu: 'એવરેસ્ટ મિલ્સ', ml: 'എവറസ്റ്റ് മിൽസ്', pa: 'ਐਵਰੈਸਟ ਮਿੱਲਜ਼',
  },
  'brand.full': {
    en: 'Everest Textile Mills', hi: 'एवरेस्ट टेक्सटाइल मिल्स', kn: 'ಎವರೆಸ್ಟ್ ಟೆಕ್ಸ್‌ಟೈಲ್ ಮಿಲ್ಸ್', ta: 'எவரெஸ்ட் டெக்ஸ்டைல் மில்ஸ்', te: 'ఎవరెస్ట్ టెక్స్‌టైల్ మిల్స్',
    mr: 'एव्हरेस्ट टेक्सटाइल मिल्स', bn: 'এভারেস্ট টেক্সটাইল মিলস', gu: 'એવરેસ્ટ ટેક્સટાઇલ મિલ્સ', ml: 'എവറസ്റ്റ് ടെക്സ്റ്റൈൽ മിൽസ്', pa: 'ਐਵਰੈਸਟ ਟੈਕਸਟਾਈਲ ਮਿੱਲਜ਼',
  },
  'common.demo': {
    en: 'Demo data', hi: 'डेमो डेटा', kn: 'ಡೆಮೊ ಡೇಟಾ', ta: 'டெமோ தரவு', te: 'డెమో డేటా',
    mr: 'डेमो डेटा', bn: 'ডেমো ডেটা', gu: 'ડેમો ડેટા', ml: 'ഡെമോ ഡാറ്റ', pa: 'ਡੈਮੋ ਡਾਟਾ',
  },
  'common.of': {
    en: '{value} of {max}', hi: '{max} में से {value}', kn: '{max} ರಲ್ಲಿ {value}', ta: '{max} இல் {value}', te: '{max} లో {value}',
    mr: '{max} पैकी {value}', bn: '{max}-এর মধ্যে {value}', gu: '{max} માંથી {value}', ml: '{max}-ൽ {value}', pa: '{max} ਵਿੱਚੋਂ {value}',
  },
  'chart.profit': {
    en: 'Profit {amount}', hi: 'मुनाफ़ा {amount}', kn: 'ಲಾಭ {amount}', ta: 'இலாபம் {amount}', te: 'లాభం {amount}',
    mr: 'नफा {amount}', bn: 'মুনাফা {amount}', gu: 'નફો {amount}', ml: 'ലാഭം {amount}', pa: 'ਮੁਨਾਫ਼ਾ {amount}',
  },
  'chart.loss': {
    en: 'Loss {amount}', hi: 'घाटा {amount}', kn: 'ನಷ್ಟ {amount}', ta: 'நட்டம் {amount}', te: 'నష్టం {amount}',
    mr: 'तोटा {amount}', bn: 'ক্ষতি {amount}', gu: 'નુકસાન {amount}', ml: 'നഷ്ടം {amount}', pa: 'ਘਾਟਾ {amount}',
  },
  'chart.revenue': {
    en: 'Revenue', hi: 'आमदनी', kn: 'ಆದಾಯ', ta: 'வருவாய்', te: 'ఆదాయం',
    mr: 'उत्पन्न', bn: 'আয়', gu: 'આવક', ml: 'വരുമാനം', pa: 'ਆਮਦਨ',
  },
  'chart.cost': {
    en: 'Cost', hi: 'लागत', kn: 'ವೆಚ್ಚ', ta: 'செலவு', te: 'ఖర్చు',
    mr: 'खर्च', bn: 'খরচ', gu: 'ખર્ચ', ml: 'ചെലവ്', pa: 'ਖ਼ਰਚਾ',
  },
  'chart.profitWord': {
    en: 'Profit', hi: 'मुनाफ़ा', kn: 'ಲಾಭ', ta: 'இலாபம்', te: 'లాభం',
    mr: 'नफा', bn: 'মুনাফা', gu: 'નફો', ml: 'ലാഭം', pa: 'ਮੁਨਾਫ਼ਾ',
  },
  'chart.note': {
    en: 'Profit or loss is written above each order', hi: 'हर ऑर्डर के ऊपर मुनाफ़ा या घाटा लिखा है', kn: 'ಪ್ರತಿ ಆರ್ಡರ್ ಮೇಲೆ ಲಾಭ ಅಥವಾ ನಷ್ಟ ಬರೆಯಲಾಗಿದೆ', ta: 'ஒவ்வொரு ஆர்டருக்கும் மேலே இலாபம் அல்லது நட்டம் எழுதப்பட்டுள்ளது', te: 'ప్రతి ఆర్డర్ పైన లాభం లేదా నష్టం రాయబడింది',
    mr: 'प्रत्येक ऑर्डरच्या वर नफा किंवा तोटा लिहिला आहे', bn: 'প্রতিটি অর্ডারের ওপরে মুনাফা বা ক্ষতি লেখা আছে', gu: 'દરેક ઓર્ડર ઉપર નફો કે નુકસાન લખ્યું છે', ml: 'ഓരോ ഓർഡറിനും മുകളിൽ ലാഭമോ നഷ്ടമോ എഴുതിയിരിക്കുന്നു', pa: 'ਹਰ ਆਰਡਰ ਦੇ ਉੱਪਰ ਮੁਨਾਫ਼ਾ ਜਾਂ ਘਾਟਾ ਲਿਖਿਆ ਹੈ',
  },
  'chart.revenueTitle': {
    en: '{label}: revenue {amount}', hi: '{label}: आमदनी {amount}', kn: '{label}: ಆದಾಯ {amount}', ta: '{label}: வருவாய் {amount}', te: '{label}: ఆదాయం {amount}',
    mr: '{label}: उत्पन्न {amount}', bn: '{label}: আয় {amount}', gu: '{label}: આવક {amount}', ml: '{label}: വരുമാനം {amount}', pa: '{label}: ਆਮਦਨ {amount}',
  },
  'chart.costTitle': {
    en: '{label}: cost {amount}', hi: '{label}: लागत {amount}', kn: '{label}: ವೆಚ್ಚ {amount}', ta: '{label}: செலவு {amount}', te: '{label}: ఖర్చు {amount}',
    mr: '{label}: खर्च {amount}', bn: '{label}: খরচ {amount}', gu: '{label}: ખર્ચ {amount}', ml: '{label}: ചെലവ് {amount}', pa: '{label}: ਖ਼ਰਚਾ {amount}',
  },
} satisfies Area
