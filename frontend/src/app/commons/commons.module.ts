import { NgModule,ModuleWithProviders } from '@angular/core';
import { CommonModule } from '@angular/common';
import {UtilsService} from '../services/utils.service'

@NgModule({
  imports: [
    CommonModule
  ],
  declarations: [],
  providers:[UtilsService]
})
export class CommonsModule { 

  constructor(utilsService: UtilsService){

  }
  static forRoot(): ModuleWithProviders {
    return {
      ngModule: CommonsModule,
      providers: [UtilsService]
    };
  }

}
