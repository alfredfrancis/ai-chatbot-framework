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

  ngOnInit() {
    this.agent_service.get_config().then(
    (result)=>{
      this.config_form.setValue(result);
    }
    )
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
