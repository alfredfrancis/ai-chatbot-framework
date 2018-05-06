import { Component, OnInit } from '@angular/core';
import { environment } from '../../../environments/environment';
import { FormGroup, FormBuilder, FormArray } from '@angular/forms';
import {IntentService} from '../../services/intent.service'
import {AgentsService} from '../../services/agents.service'

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss']
})
export class SettingsComponent implements OnInit {

  fileToUpload: File = null;
  config_form =  this.fb.group({
    "confidence_threshold":[]
  });

  constructor(private intentService:IntentService,private agent_service:AgentsService,  public fb: FormBuilder) { }

  code = `
  
  <script type="text/javascript">
  !function(win,doc){"use strict";var script_loader=(iky_base_url)=>{win.iky_base_url=iky_base_url;try
  {var r=doc.head||doc.getElementsByTagName("head")[0],a=doc.createElement("script");a.setAttribute("type","text/javascript"),a.setAttribute("src",iky_base_url+"assets/widget/iky_widget.js"),r.appendChild(a)}
  catch(e){}};win.chat_context={"username":"Alfred"},script_loader("http://localhost:8080/")}(window,document);
  </script>
  `
  ngOnInit() {
    this.agent_service.get_config().then(
    (result)=>{
      this.config_form.setValue(result);
    }
    )
  }

  threshold_value_changed(){
    this.save_config()
  }
  save_config(){
    this.agent_service.update_config(this.config_form.value)
    console.log(this.config_form.value)
  }

  export(){
    window.open(environment.ikyBackend+"intents/export","_blank")
  }
  handleFileInput(files: FileList) {
    this.fileToUpload = files.item(0);
  }

uploadFileToActivity() {
  this.intentService.importIntents(this.fileToUpload).then ((result)=>{
    console.log(result)
  })
}

}
