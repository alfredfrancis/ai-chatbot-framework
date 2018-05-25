import { Injectable } from '@angular/core';
import { FormGroup } from '@angular/forms';
import { BehaviorSubject } from 'rxjs/BehaviorSubject';

@Injectable()
export class UtilsService {

  public status: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(false);

  constructor() { }

  setDataForm(form, keys, data) {
    if (!data) { return; }
    const formData = {};
    for (const key in keys) {
      if (key in data) {
        const value = data[key];
        formData[key] = value;
      } else { formData[key] = ''; }
    }
    // (<FormGroup>form).setValue(formData, { onlySelf: true });
    (<FormGroup>form).patchValue(formData, { onlySelf: true });
  }


  displayLoader(value: boolean) {
      this.status.next(value);
      console.log("loader",value)
  }


}
