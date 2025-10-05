function createForm() {



      chrome.storage.sync.get(['removedContextMenu'], function (list) {
            let removed = list.removedContextMenu || [];
            let form = document.getElementById('form');

            //Separate checkboxes to two parts ( not equal )
            let divEnd = 16;
            let divClass = 'left_menu';
            let i = 0;
            //The div cointaing the checkboxes
            let theDiv = document.createElement('div');
            theDiv.className = 'left_menu';
            //For separation from the object "sep"
            let borderTop = '';

            for (let key of Object.keys(kLocales)) {
                  i++;
                  if (divEnd === i) {
                        form.appendChild(theDiv);
                        theDiv = document.createElement('div');
                        theDiv.className = 'right_menu';
                  }
                  //It is auto sorting object if the key is number?!?
                  if (kLocales[key] == 'sep') {
                        borderTop = ' border_top';
                        continue;
                  } else {
                        let div = document.createElement('div');
                        div.className = 'checkbox' + borderTop;

                        let checked = 'checked';
                        if (removed.includes(key)) {
                              checked = '';
                        }

                        div.innerHTML = "<label><input " + checked + " type='checkbox' name='" + key + "' value='" + kLocales[key] + "'><span>" + kLocales[key] + "</span></label>";

                        theDiv.appendChild(div);
                        borderTop = '';
                  }
            }
            form.appendChild(theDiv);
      });
}

createForm();

document.getElementById('optionsSubmit').onclick = function () {
      let input = document.getElementsByTagName('input');
      let removed = [];
      for (i = 0; i < input.length; i++) {
            if (input[i].checked == false && (input[i].name !== 'api_key' && input[i].name !== 'api_sig')) {
                  removed.push(input[i].name);
            }
      }
      chrome.storage.sync.set({removedContextMenu: removed});
      let form = document.getElementById('form');
      form.innerHTML = '<p>Option saved. <br><br>Closing ...</p></div>';

      setTimeout(function () {
            window.close();
      }, 3000);
}
