chrome.runtime.onInstalled.addListener(function (details) {


  if (details.reason == "install") {

    chrome.storage.local.get(['ge-local-user-details'], function (userInformation) {

      if (Object.keys(userInformation).length == 0) {
        let userInformationJSON = {
          "unique-system-code": new Date().valueOf(),
          "date-time-of-install": new Date().toLocaleString()
        }
        chrome.storage.local.set({ 'ge-local-user-details': userInformationJSON }, function (result) {
        });

      }

    });

    chrome.tabs.create({
      url: "https://link.gmbeverywhere.com/on-install-page",
      active: true,
    });
  }
  if (details.reason == 'update') {
    chrome.tabs.create({
      url: "https://www.gmbeverywhere.com/update-page",
      active: true,
    });
  }

  return;
});

chrome.runtime.setUninstallURL("https://link.gmbeverywhere.com/on-uninstall-page");

chrome.action.onClicked.addListener((tab) => {
  chrome.tabs.create({ url: "https://www.google.com/maps/search/dentist%20nearby" });
});