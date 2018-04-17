import { Component, OnInit } from '@angular/core';
import { environment } from '../../../environments/environment';

import {IntentService} from '../../services/intent.service'
@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss']
})
export class SettingsComponent implements OnInit {

  fileToUpload: File = null;
  constructor(private intentService:IntentService) { }

  ngOnInit() {
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
