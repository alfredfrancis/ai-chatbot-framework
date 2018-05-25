import { Component, OnInit } from '@angular/core';
import {UtilsService} from './services/utils.service'

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent  implements OnInit {
  title = 'app';
  showLoader: boolean;

  constructor(
    private coreService: UtilsService) {
}
ngOnInit() {
  this.coreService.status.subscribe((val: boolean) => {
    console.log("value changed")
      this.showLoader = val;
  });
}
}
